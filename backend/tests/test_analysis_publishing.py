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


def add_case(db: Session, *, analysis_version: int = 0) -> models.Case:
    case = models.Case(
        title="分析发布测试",
        claimant="甲",
        employer="乙",
        raw_facts="用于满足工作流输入步骤的事实。",
        workflow_mode="ai_case",
        material_version=2,
        fact_version=3,
        issue_version=4,
        analysis_version=analysis_version,
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
    issue = models.CaseIssue(
        case_id=case.id,
        title="已发布争点",
        status="人工确认",
        fact_version=case.fact_version,
        issue_version=case.issue_version,
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)
    return case


def case_issue(db: Session, case: models.Case) -> models.CaseIssue:
    return db.query(models.CaseIssue).filter_by(case_id=case.id).one()


def add_analysis(
    db: Session,
    case: models.Case,
    *,
    review_status: str = "已接受",
    material_version: int | None = None,
    fact_version: int | None = None,
    issue_version: int | None = None,
    analysis_version: int = 0,
    output_version: int = 1,
    unit: models.WorkUnit | None = None,
) -> models.AIOutput:
    issue = case_issue(db, case)
    if unit is None:
        unit = models.WorkUnit(
            case_id=case.id,
            code=f"legal_analysis:{issue.id}",
            title=f"法律分析：{issue.title}",
            sequence=3,
            status="已批准",
            parent_issue_id=issue.id,
        )
        db.add(unit)
        db.flush()
    output = models.AIOutput(
        case_id=case.id,
        work_unit_id=unit.id,
        output_type="legal_analysis",
        title=f"法律分析：{issue.title}",
        content=f"分析正文 V{output_version}",
        review_status=review_status,
        version=output_version,
        material_version=(
            case.material_version if material_version is None else material_version
        ),
        fact_version=case.fact_version if fact_version is None else fact_version,
        issue_version=case.issue_version if issue_version is None else issue_version,
        analysis_version=analysis_version,
    )
    db.add(output)
    db.commit()
    db.refresh(output)
    return output


def request_payload(
    analysis_ids: list[int],
    *,
    operation_id: str = "publish-analyses-001",
) -> schemas.AnalysisPublishRequest:
    return schemas.AnalysisPublishRequest(
        analysis_ids=analysis_ids,
        operation_id=operation_id,
        reason="完整分析集已通过律师审核",
    )


def publish(
    db: Session,
    case_id: int,
    analysis_ids: list[int],
    *,
    operation_id: str = "publish-analyses-001",
) -> schemas.AnalysisPublishOut:
    return main.publish_analyses(
        case_id,
        request_payload(analysis_ids, operation_id=operation_id),
        db,
        idempotency_key=operation_id,
    )


def test_analysis_publish_api_advances_version_and_records_event(db: Session) -> None:
    case = add_case(db)
    output = add_analysis(db, case)

    def override_db():
        yield db

    main.app.dependency_overrides[main.get_db] = override_db
    try:
        response = TestClient(main.app).post(
            f"/cases/{case.id}/analyses/publish",
            json={
                "analysis_ids": [output.id],
                "operation_id": "publish-analyses-via-api",
                "reason": "API 发布完整分析集",
            },
            headers={"Idempotency-Key": "publish-analyses-via-api"},
        )
    finally:
        main.app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["case_id"] == case.id
    assert (payload["old_version"], payload["new_version"]) == (0, 1)
    assert payload["analysis_ids"] == [output.id]
    assert len(payload["analysis_digest"]) == 64
    assert payload["replayed"] is False
    db.refresh(case)
    db.refresh(output)
    assert case.analysis_version == 1
    assert output.analysis_version == 1

    event = db.query(models.WorkflowEvent).filter_by(
        case_id=case.id,
        event_type="ANALYSIS_VERSION_PUBLISHED",
    ).one()
    event_payload = json.loads(event.payload_json)
    assert event_payload["analysis_ids"] == [output.id]
    assert event_payload["analysis_digest"] == payload["analysis_digest"]
    assert event_payload["source"] == "analyses_publish"
    assert event_payload["operation_id"] == "publish-analyses-via-api"


def test_repeated_analysis_publish_is_idempotent(db: Session) -> None:
    case = add_case(db)
    output = add_analysis(db, case, review_status="已修改")

    first = publish(db, case.id, [output.id])
    repeated = publish(db, case.id, [output.id])
    db.refresh(case)

    assert first.replayed is False
    assert repeated == first.model_copy(update={"replayed": True})
    assert case.analysis_version == 1
    assert db.query(models.WorkflowEvent).filter_by(
        case_id=case.id,
        event_type="ANALYSIS_VERSION_PUBLISHED",
    ).count() == 1


def test_stale_analysis_is_rejected(db: Session) -> None:
    case = add_case(db)
    output = add_analysis(db, case, material_version=case.material_version - 1)

    with pytest.raises(HTTPException) as exc_info:
        publish(db, case.id, [output.id])

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["analysis_ids"] == [output.id]
    db.refresh(case)
    db.refresh(output)
    assert case.analysis_version == 0
    assert output.analysis_version == 0


def test_unreviewed_analysis_is_rejected(db: Session) -> None:
    case = add_case(db)
    output = add_analysis(db, case, review_status="待复核")

    with pytest.raises(HTTPException) as exc_info:
        publish(db, case.id, [output.id])

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["analysis_ids"] == [output.id]
    db.refresh(case)
    assert case.analysis_version == 0


@pytest.mark.parametrize("version_field", ["fact_version", "issue_version"])
def test_analysis_publish_requires_published_input_versions(
    db: Session,
    version_field: str,
) -> None:
    case = add_case(db)
    output = add_analysis(db, case)
    setattr(case, version_field, 0)
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        publish(db, case.id, [output.id])

    assert exc_info.value.status_code == 409
    db.refresh(case)
    assert case.analysis_version == 0


def test_foreign_and_non_legal_analysis_outputs_are_rejected(db: Session) -> None:
    case = add_case(db)
    own_output = add_analysis(db, case)
    other_case = add_case(db)
    foreign_output = add_analysis(db, other_case)

    with pytest.raises(HTTPException) as foreign_error:
        publish(db, case.id, [foreign_output.id], operation_id="foreign-analysis")
    assert foreign_error.value.status_code == 409
    assert foreign_error.value.detail["analysis_ids"] == [foreign_output.id]

    own_output.output_type = "legal_report"
    db.commit()
    with pytest.raises(HTTPException) as type_error:
        publish(db, case.id, [own_output.id], operation_id="wrong-output-type")
    assert type_error.value.status_code == 409
    assert type_error.value.detail["analysis_ids"] == [own_output.id]
    db.refresh(case)
    assert case.analysis_version == 0


def test_analysis_publish_rolls_back_version_output_and_event(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = add_case(db)
    output = add_analysis(db, case)

    def fail_commit() -> None:
        raise RuntimeError("simulated commit failure")

    monkeypatch.setattr(db, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="simulated commit failure"):
        publish(db, case.id, [output.id])

    db.expire_all()
    stored_case = db.get(models.Case, case.id)
    stored_output = db.get(models.AIOutput, output.id)
    assert stored_case is not None and stored_case.analysis_version == 0
    assert stored_output is not None and stored_output.analysis_version == 0
    assert db.query(models.WorkflowEvent).filter_by(
        case_id=case.id,
        event_type="ANALYSIS_VERSION_PUBLISHED",
    ).count() == 0


def test_workflow_state_switches_to_new_published_analysis_version(db: Session) -> None:
    case = add_case(db, analysis_version=1)
    old = add_analysis(
        db,
        case,
        material_version=case.material_version - 1,
        analysis_version=1,
        output_version=1,
    )
    unit = db.get(models.WorkUnit, old.work_unit_id)
    current = add_analysis(
        db,
        case,
        analysis_version=0,
        output_version=2,
        unit=unit,
    )

    before = compute_workflow_state(db, case)
    assert before.current_step == "legal_analysis"
    assert before.next_action is not None
    assert before.next_action.code == "ANALYSIS_STALE"
    assert before.coverage.analysis.stale == 1

    result = publish(db, case.id, [current.id], operation_id="publish-current-analysis")
    assert result.new_version == 2
    db.refresh(case)
    after = compute_workflow_state(db, case)

    assert case.analysis_version == 2
    assert after.current_step == "report"
    assert after.next_action is not None
    assert after.next_action.code == "REPORT_MISSING"
    assert after.coverage.analysis.generated == 1
    assert after.coverage.analysis.approved == 1
    assert after.coverage.analysis.stale == 0
    assert after.analysis_count == 1
    assert after.approved_analysis_count == 1
