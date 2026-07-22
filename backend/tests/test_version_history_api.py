from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import main, models


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


@pytest.fixture()
def client(db: Session):
    def override_db():
        yield db

    main.app.dependency_overrides[main.get_db] = override_db
    try:
        yield TestClient(main.app)
    finally:
        main.app.dependency_overrides.clear()


def seed_history(db: Session) -> models.Case:
    now = datetime.utcnow()
    case = models.Case(
        title="历史接口测试",
        claimant="甲",
        employer="乙",
        material_version=1,
        fact_version=1,
        issue_version=0,
        analysis_version=0,
        report_version=0,
    )
    db.add(case)
    db.flush()
    output = models.AIOutput(
        case_id=case.id,
        output_type="fact_extraction",
        title="事实提取",
        content="生成内容",
        version=3,
        material_version=1,
        fact_version=0,
        issue_version=0,
        analysis_version=0,
        report_version=0,
        created_at=now,
    )
    db.add(output)
    db.add(models.WorkflowEvent(
        case_id=case.id,
        event_type="FACT_VERSION_PUBLISHED",
        message="事实已发布",
        payload_json=json.dumps({
            "old_version": 0,
            "new_version": 1,
            "material_version": 1,
            "fact_ids": [11, 12],
            "reason": "人工确认后发布",
        }),
        created_at=now + timedelta(seconds=1),
    ))
    db.add(models.DecisionTrace(
        case_id=case.id,
        ai_output_id=output.id,
        ai_suggestion="AI 事实",
        human_revision="律师事实",
        revision_reason="核对证据",
        tags="事实,修改",
        action="修改",
        object_type="事实",
        object_id=11,
        created_at=now + timedelta(seconds=2),
    ))
    db.commit()
    db.refresh(case)
    return case


def test_version_history_contract_distinguishes_generation_and_publication(
    db: Session,
    client: TestClient,
) -> None:
    case = seed_history(db)

    response = client.get(f"/cases/{case.id}/version-history?page=1&page_size=1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_versions"] == {
        "material_version": 1,
        "fact_version": 1,
        "issue_version": 0,
        "analysis_version": 0,
        "report_version": 0,
    }
    assert payload["total"] == 2
    assert payload["page"] == 1
    assert payload["page_size"] == 1
    published = payload["items"][0]
    assert published["entry_type"] == "publication"
    assert published["generation_version"] is None
    assert published["published_version"] == 1
    assert published["before_versions"]["fact_version"] == 0
    assert published["after_versions"]["fact_version"] == 1

    generated = client.get(
        f"/cases/{case.id}/version-history?page=2&page_size=1"
    ).json()["items"][0]
    assert generated["entry_type"] == "generation"
    assert generated["generation_version"] == 3
    assert generated["published_version"] is None
    assert generated["input_versions"]["fact_version"] == 0


def test_reasoning_trace_contract_uses_null_for_missing_legacy_fields(
    db: Session,
    client: TestClient,
) -> None:
    case = seed_history(db)

    response = client.get(f"/cases/{case.id}/reasoning-trace")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    decision, publication = payload["items"]
    assert decision["event_source"] == "decision_trace"
    assert decision["ai_suggestion"] == "AI 事实"
    assert decision["before_versions"] is None
    assert decision["after_versions"] is None
    assert publication["event_source"] == "workflow_event"
    assert publication["ai_suggestion"] is None
    assert publication["human_revision"] is None
    assert publication["tags"] is None
    assert publication["before_versions"]["fact_version"] == 0
    assert publication["after_versions"]["fact_version"] == 1


def test_version_zero_remains_unpublished(db: Session, client: TestClient) -> None:
    case = models.Case(
        title="旧案件",
        claimant="甲",
        employer="乙",
        material_version=1,
        fact_version=0,
        issue_version=0,
        analysis_version=0,
        report_version=0,
    )
    db.add(case)
    db.add(models.AIOutput(
        case=case,
        output_type="legal_analysis",
        title="旧分析",
        content="旧内容",
        version=1,
        material_version=1,
        fact_version=0,
        issue_version=0,
        analysis_version=0,
        report_version=0,
    ))
    db.commit()

    payload = client.get(f"/cases/{case.id}/version-history").json()

    assert payload["current_versions"]["analysis_version"] == 0
    assert payload["items"][0]["generation_version"] == 1
    assert payload["items"][0]["published_version"] is None


def test_history_pagination_validation(client: TestClient, db: Session) -> None:
    case = seed_history(db)
    assert client.get(f"/cases/{case.id}/version-history?page=0").status_code == 422
    assert client.get(f"/cases/{case.id}/reasoning-trace?page_size=101").status_code == 422


def test_older_generation_is_not_marked_current(
    db: Session,
    client: TestClient,
) -> None:
    case = seed_history(db)
    existing = db.query(models.AIOutput).filter_by(case_id=case.id).one()
    newer = models.AIOutput(
        case_id=case.id,
        work_unit_id=existing.work_unit_id,
        output_type=existing.output_type,
        title="事实提取重跑",
        content="较新生成内容",
        version=existing.version + 1,
        material_version=case.material_version,
        fact_version=case.fact_version,
        issue_version=case.issue_version,
    )
    db.add(newer)
    db.commit()

    items = client.get(f"/cases/{case.id}/version-history?page_size=100").json()["items"]
    generations = [item for item in items if item["entry_type"] == "generation"]
    by_id = {item["ai_output_id"]: item for item in generations}

    assert by_id[newer.id]["is_current"] is True
    assert by_id[existing.id]["is_current"] is False
    assert by_id[existing.id]["is_stale"] is True
    assert by_id[existing.id]["stale_reason"] == "generation_superseded"


def test_history_and_trace_gets_do_not_write(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = seed_history(db)

    def forbidden_write(*_args, **_kwargs):
        raise AssertionError("read-model endpoint attempted a database write")

    monkeypatch.setattr(db, "add", forbidden_write)
    monkeypatch.setattr(db, "delete", forbidden_write)
    monkeypatch.setattr(db, "flush", forbidden_write)
    monkeypatch.setattr(db, "commit", forbidden_write)

    history = main.version_history(case.id, 1, 25, db)
    trace = main.reasoning_trace(case.id, 1, 25, db)

    assert history.total == 2
    assert trace.total == 2
    assert list(db.new) == []
    assert list(db.dirty) == []
    assert list(db.deleted) == []
