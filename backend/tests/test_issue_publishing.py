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
        title="争点发布测试",
        claimant="甲",
        employer="乙",
        raw_facts="用于满足案件输入和材料步骤的现场事实。",
        workflow_mode="ai_case",
        material_version=4,
        fact_version=3,
        issue_version=2,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    db.add(models.CaseFact(
        case_id=case.id,
        ai_fact="已发布事实",
        human_fact="已发布事实",
        status="已确认",
        material_version=case.material_version,
        fact_version=case.fact_version,
    ))
    db.commit()
    return case


def add_issue(
    db: Session,
    case: models.Case,
    *,
    status: str = "人工确认",
    fact_version: int | None = None,
) -> models.CaseIssue:
    issue = models.CaseIssue(
        case_id=case.id,
        title="待发布争点",
        description="争点描述",
        status=status,
        fact_version=(
            case.fact_version - 1
            if fact_version is None
            else fact_version
        ),
        issue_version=case.issue_version,
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)
    return issue


def publish(
    db: Session,
    case_id: int,
    *,
    operation_id: str = "publish-issues-001",
) -> schemas.IssuePublishOut:
    return main.publish_issues(
        case_id,
        schemas.IssuePublishRequest(
            operation_id=operation_id,
            reason="争点集已完成律师审核",
        ),
        db,
        idempotency_key=operation_id,
    )


def test_issue_publish_advances_once_and_stamps_lineage(db: Session) -> None:
    case = add_case(db)
    first = add_issue(db, case)
    second = add_issue(db, case, status="已完成")

    result = publish(db, case.id)
    db.refresh(case)
    db.refresh(first)
    db.refresh(second)

    assert result == schemas.IssuePublishOut(
        case_id=case.id,
        old_version=2,
        new_version=3,
        fact_version=3,
        issue_ids=[first.id, second.id],
        replayed=False,
    )
    assert case.issue_version == 3
    assert {first.issue_version, second.issue_version} == {3}
    assert {first.fact_version, second.fact_version} == {3}

    event = db.query(models.WorkflowEvent).filter_by(
        case_id=case.id,
        event_type="ISSUE_VERSION_PUBLISHED",
    ).one()
    assert json.loads(event.payload_json) == {
        "old_version": 2,
        "new_version": 3,
        "fact_version": 3,
        "issue_ids": [first.id, second.id],
        "reason": "争点集已完成律师审核",
        "source": "issues_publish",
        "operation_id": "publish-issues-001",
    }


def test_issue_publish_api_accepts_idempotency_key(db: Session) -> None:
    case = add_case(db)
    issue = add_issue(db, case)

    def override_db():
        yield db

    main.app.dependency_overrides[main.get_db] = override_db
    try:
        response = TestClient(main.app).post(
            f"/cases/{case.id}/issues/publish",
            json={
                "operation_id": "publish-issues-via-api",
                "reason": "API 发布争点集",
            },
            headers={"Idempotency-Key": "publish-issues-via-api"},
        )
    finally:
        main.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "case_id": case.id,
        "old_version": 2,
        "new_version": 3,
        "fact_version": 3,
        "issue_ids": [issue.id],
        "replayed": False,
    }


def test_issue_publish_requires_a_published_fact_version(db: Session) -> None:
    case = add_case(db)
    add_issue(db, case)
    case.fact_version = 0
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        publish(db, case.id)

    assert exc_info.value.status_code == 409
    db.refresh(case)
    assert case.issue_version == 2
    assert db.query(models.WorkflowEvent).filter_by(
        case_id=case.id,
        event_type="ISSUE_VERSION_PUBLISHED",
    ).count() == 0


def test_single_issue_update_does_not_advance_version(db: Session) -> None:
    case = add_case(db)
    issue = add_issue(db, case, fact_version=case.fact_version)

    main.update_issue(
        issue.id,
        schemas.IssueUpdate(
            title="律师修改后的争点",
            description="修改后的描述",
            status="人工确认",
            reason="根据事实调整争点",
        ),
        db,
    )
    db.refresh(case)
    db.refresh(issue)

    assert case.issue_version == 2
    assert issue.issue_version == 2
    assert issue.title == "律师修改后的争点"


def test_single_issue_confirmation_does_not_advance_version(db: Session) -> None:
    case = add_case(db)
    issue = add_issue(db, case, status="AI建议", fact_version=case.fact_version)

    main.issue_action(
        issue.id,
        schemas.IssueAction(action="确认", reason="律师确认争点"),
        db,
    )
    db.refresh(case)
    db.refresh(issue)

    assert case.issue_version == 2
    assert issue.issue_version == 2
    assert issue.status == "人工确认"


def test_batch_issue_confirmation_does_not_advance_version(db: Session) -> None:
    case = add_case(db)
    first = add_issue(db, case, status="AI建议", fact_version=case.fact_version)
    second = add_issue(db, case, status="AI建议", fact_version=case.fact_version)

    main.confirm_all_issues(
        case.id,
        schemas.BatchReview(reason="完成争点集批量审核"),
        db,
    )
    db.refresh(case)
    db.refresh(first)
    db.refresh(second)

    assert case.issue_version == 2
    assert {first.issue_version, second.issue_version} == {2}
    assert {first.status, second.status} == {"人工确认"}


def test_ai_issue_draft_generation_does_not_advance_version(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = add_case(db)
    add_issue(db, case, status="AI建议", fact_version=case.fact_version)
    unit = models.WorkUnit(
        case_id=case.id,
        code="issue_identification",
        title="争点识别",
        sequence=1,
        status="待处理",
    )
    db.add(unit)
    db.commit()

    monkeypatch.setattr(main, "issue_identification", lambda *_args: {
        "issues": [{
            "title": "新增争点草稿",
            "description": "草稿描述",
            "related_fact_ids": [],
        }],
    })
    main.run_ai_issue_identification(db, case, unit)
    db.refresh(case)

    draft = db.query(models.CaseIssue).filter_by(
        case_id=case.id,
        title="新增争点草稿",
    ).one()
    assert case.issue_version == 2
    assert draft.issue_version == 2
    assert draft.fact_version == case.fact_version


def test_issue_publish_rolls_back_version_rows_and_event(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = add_case(db)
    issue = add_issue(db, case)

    def fail_commit() -> None:
        raise RuntimeError("simulated commit failure")

    monkeypatch.setattr(db, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="simulated commit failure"):
        publish(db, case.id)

    db.expire_all()
    stored_case = db.get(models.Case, case.id)
    stored_issue = db.get(models.CaseIssue, issue.id)
    assert stored_case is not None and stored_case.issue_version == 2
    assert stored_issue is not None and stored_issue.issue_version == 2
    assert stored_issue.fact_version == 2
    assert db.query(models.WorkflowEvent).filter_by(
        case_id=case.id,
        event_type="ISSUE_VERSION_PUBLISHED",
    ).count() == 0


def test_repeated_operation_id_replays_first_issue_publish(db: Session) -> None:
    case = add_case(db)
    add_issue(db, case)

    first = publish(db, case.id)
    repeated = publish(db, case.id)
    db.refresh(case)

    assert first.replayed is False
    assert repeated == first.model_copy(update={"replayed": True})
    assert case.issue_version == 3
    assert db.query(models.WorkflowEvent).filter_by(
        case_id=case.id,
        event_type="ISSUE_VERSION_PUBLISHED",
    ).count() == 1


def test_workflow_state_recovers_after_issue_publish(db: Session) -> None:
    case = add_case(db)
    add_issue(db, case)

    before = compute_workflow_state(db, case)
    assert any(blocker.code == "ISSUES_STALE" for blocker in before.blockers)

    publish(db, case.id)
    db.refresh(case)
    after = compute_workflow_state(db, case)

    assert after.current_step == "legal_analysis"
    assert after.issues_confirmed is True
    assert after.coverage.issues.stale == 0
    assert all(blocker.code != "ISSUES_STALE" for blocker in after.blockers)
    assert after.next_action is not None
    assert after.next_action.code == "ANALYSIS_MISSING"
