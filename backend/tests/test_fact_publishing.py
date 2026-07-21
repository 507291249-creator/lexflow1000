from __future__ import annotations

import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import main, models, schemas
from app.services.workflow import compute_workflow_state


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def add_case(db: Session) -> models.Case:
    case = models.Case(
        title="事实发布测试",
        claimant="甲",
        employer="乙",
        raw_facts="用于满足案件输入和材料步骤的现场事实。",
        workflow_mode="ai_case",
        material_version=4,
        fact_version=2,
        issue_version=1,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def add_fact(
    db: Session,
    case: models.Case,
    *,
    status: str = "已确认",
    material_version: int | None = None,
) -> models.CaseFact:
    fact = models.CaseFact(
        case_id=case.id,
        ai_fact="AI 事实",
        human_fact="已确认事实" if status == "已确认" else "",
        status=status,
        material_version=(
            case.material_version - 1
            if material_version is None
            else material_version
        ),
        fact_version=case.fact_version,
    )
    db.add(fact)
    db.commit()
    db.refresh(fact)
    return fact


def publish(
    db: Session,
    case_id: int,
    *,
    operation_id: str = "publish-facts-001",
) -> schemas.FactPublishOut:
    return main.publish_facts(
        case_id,
        schemas.FactPublishRequest(
            operation_id=operation_id,
            reason="事实集已完成律师复核",
        ),
        db,
        idempotency_key=operation_id,
    )


def test_fact_publish_advances_once_and_stamps_lineage(db: Session) -> None:
    case = add_case(db)
    confirmed = add_fact(db, case)
    rejected = add_fact(db, case, status="已驳回")

    result = publish(db, case.id)
    db.refresh(case)
    db.refresh(confirmed)
    db.refresh(rejected)

    assert result == schemas.FactPublishOut(
        case_id=case.id,
        old_version=2,
        new_version=3,
        material_version=4,
        fact_ids=[confirmed.id, rejected.id],
        replayed=False,
    )
    assert case.fact_version == 3
    assert {confirmed.fact_version, rejected.fact_version} == {3}
    assert {confirmed.material_version, rejected.material_version} == {4}

    event = db.query(models.WorkflowEvent).filter_by(
        case_id=case.id,
        event_type="FACT_VERSION_PUBLISHED",
    ).one()
    assert json.loads(event.payload_json) == {
        "old_version": 2,
        "new_version": 3,
        "material_version": 4,
        "fact_ids": [confirmed.id, rejected.id],
        "reason": "事实集已完成律师复核",
        "source": "facts_publish",
        "operation_id": "publish-facts-001",
    }


def test_fact_publish_api_accepts_idempotency_key(db: Session) -> None:
    case = add_case(db)
    fact = add_fact(db, case)

    def override_db():
        yield db

    main.app.dependency_overrides[main.get_db] = override_db
    try:
        response = TestClient(main.app).post(
            f"/cases/{case.id}/facts/publish",
            json={
                "operation_id": "publish-via-api",
                "reason": "API 发布事实集",
            },
            headers={"Idempotency-Key": "publish-via-api"},
        )
    finally:
        main.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "case_id": case.id,
        "old_version": 2,
        "new_version": 3,
        "material_version": 4,
        "fact_ids": [fact.id],
        "replayed": False,
    }


def test_single_fact_edit_does_not_advance_version(db: Session) -> None:
    case = add_case(db)
    fact = add_fact(db, case, status="待确认", material_version=case.material_version)

    main.review_fact(
        fact.id,
        schemas.FactReview(
            action="修改",
            human_fact="律师修订后的事实",
            reason="根据材料修正文义",
        ),
        db,
    )
    db.refresh(case)
    db.refresh(fact)

    assert case.fact_version == 2
    assert fact.fact_version == 2
    assert fact.status == "已确认"
    assert fact.human_fact == "律师修订后的事实"


def test_batch_fact_confirmation_does_not_advance_version(db: Session) -> None:
    case = add_case(db)
    fact = add_fact(db, case, status="待确认", material_version=case.material_version)

    main.confirm_all_facts(
        case.id,
        schemas.BatchReview(reason="完成事实集批量复核"),
        db,
    )
    db.refresh(case)
    db.refresh(fact)

    assert case.fact_version == 2
    assert fact.fact_version == 2
    assert fact.status == "已确认"


def test_fact_draft_generation_does_not_advance_version(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = add_case(db)
    add_fact(db, case, status="待确认", material_version=case.material_version)
    unit = models.WorkUnit(
        case_id=case.id,
        code="fact_extraction",
        title="事实提取",
        sequence=1,
        status="待处理",
    )
    db.add(unit)
    db.commit()

    monkeypatch.setattr(main, "fact_extraction", lambda *_args: {
        "case_summary": "测试摘要",
        "parties": {},
        "key_facts": [{"content": "新增事实草稿", "category": "一般事实"}],
        "pending_facts": [],
    })
    main.run_ai_fact_extraction(db, case, unit)
    db.refresh(case)

    draft = db.query(models.CaseFact).filter_by(
        case_id=case.id,
        ai_fact="新增事实草稿",
    ).one()
    assert case.fact_version == 2
    assert draft.fact_version == 2
    assert draft.material_version == case.material_version


def test_fact_publish_rolls_back_version_rows_and_event(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = add_case(db)
    fact = add_fact(db, case)

    def fail_commit() -> None:
        raise RuntimeError("simulated commit failure")

    monkeypatch.setattr(db, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="simulated commit failure"):
        publish(db, case.id)

    db.expire_all()
    stored_case = db.get(models.Case, case.id)
    stored_fact = db.get(models.CaseFact, fact.id)
    assert stored_case is not None and stored_case.fact_version == 2
    assert stored_fact is not None and stored_fact.fact_version == 2
    assert stored_fact.material_version == 3
    assert db.query(models.WorkflowEvent).filter_by(
        case_id=case.id,
        event_type="FACT_VERSION_PUBLISHED",
    ).count() == 0


def test_repeated_operation_id_replays_first_publish(db: Session) -> None:
    case = add_case(db)
    add_fact(db, case)

    first = publish(db, case.id)
    repeated = publish(db, case.id)
    db.refresh(case)

    assert first.replayed is False
    assert repeated == first.model_copy(update={"replayed": True})
    assert case.fact_version == 3
    assert db.query(models.WorkflowEvent).filter_by(
        case_id=case.id,
        event_type="FACT_VERSION_PUBLISHED",
    ).count() == 1


def test_idempotency_header_must_match_operation_id(db: Session) -> None:
    case = add_case(db)
    add_fact(db, case)

    with pytest.raises(HTTPException) as exc_info:
        main.publish_facts(
            case.id,
            schemas.FactPublishRequest(
                operation_id="body-operation",
                reason="事实集发布",
            ),
            db,
            idempotency_key="header-operation",
        )

    assert exc_info.value.status_code == 409
    db.refresh(case)
    assert case.fact_version == 2


def test_workflow_state_recognizes_published_fact_version(db: Session) -> None:
    case = add_case(db)
    add_fact(db, case)

    publish(db, case.id)
    db.refresh(case)
    state = compute_workflow_state(db, case)

    assert state.current_step == "issue_review"
    assert state.facts_confirmed is True
    assert state.coverage.facts.stale == 0
    assert all(blocker.code != "FACTS_STALE" for blocker in state.blockers)
    assert state.next_action is not None
    assert state.next_action.code == "ISSUES_MISSING"
