from __future__ import annotations

import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import main, models, schemas
from app.services.versioning import advance_material_version
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


def build_report_draft(db: Session) -> tuple[models.Case, models.AIOutput, models.AIOutput]:
    case = models.Case(
        title="最终版本链测试",
        claimant="甲",
        employer="乙",
        summary="案件摘要",
        raw_facts="案件原始事实",
        workflow_mode="ai_case",
        material_version=1,
        fact_version=0,
        issue_version=0,
        analysis_version=0,
        report_version=0,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    db.add(models.CaseFact(
        case_id=case.id,
        ai_fact="已审核事实",
        human_fact="已审核事实",
        status="已确认",
        material_version=case.material_version,
        fact_version=case.fact_version,
    ))
    db.commit()
    main.publish_facts(
        case.id,
        schemas.FactPublishRequest(
            operation_id="chain-facts",
            reason="最终链发布事实",
        ),
        db,
    )
    db.refresh(case)

    issue = models.CaseIssue(
        case_id=case.id,
        title="已审核争点",
        description="争点描述",
        status="人工确认",
        fact_version=case.fact_version,
        issue_version=case.issue_version,
    )
    db.add(issue)
    db.commit()
    main.publish_issues(
        case.id,
        schemas.IssuePublishRequest(
            operation_id="chain-issues",
            reason="最终链发布争点",
        ),
        db,
    )
    db.refresh(case)
    db.refresh(issue)

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
    analysis = models.AIOutput(
        case_id=case.id,
        work_unit_id=unit.id,
        output_type="legal_analysis",
        title=f"法律分析：{issue.title}",
        content="正式分析正文 V1",
        review_status="已接受",
        version=1,
        material_version=case.material_version,
        fact_version=case.fact_version,
        issue_version=case.issue_version,
        analysis_version=0,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    main.publish_analyses(
        case.id,
        schemas.AnalysisPublishRequest(
            analysis_ids=[analysis.id],
            operation_id="chain-analyses",
            reason="最终链发布分析",
        ),
        db,
    )
    db.refresh(case)
    db.refresh(analysis)

    report = main.generate_legal_report(db, case)
    db.commit()
    db.refresh(report)
    return case, analysis, report


def report_publish_payload(operation_id: str = "chain-report") -> schemas.ReportPublishRequest:
    return schemas.ReportPublishRequest(
        operation_id=operation_id,
        reason="最终链发布报告",
    )


def publish_report(
    db: Session,
    case: models.Case,
    report: models.AIOutput,
    *,
    operation_id: str = "chain-report",
):
    return main.publish_report(
        case.id,
        report.id,
        report_publish_payload(operation_id),
        db,
        idempotency_key=operation_id,
    )


def test_complete_version_chain_finishes_case_lifecycle(db: Session) -> None:
    case, analysis, report = build_report_draft(db)

    def override_db():
        yield db

    main.app.dependency_overrides[main.get_db] = override_db
    try:
        response = TestClient(main.app).post(
            f"/cases/{case.id}/reports/{report.id}/publish",
            json={
                "operation_id": "chain-report-api",
                "reason": "通过 API 发布最终报告",
            },
            headers={"Idempotency-Key": "chain-report-api"},
        )
    finally:
        main.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["analysis_ids"] == [analysis.id]
    db.refresh(case)
    db.refresh(report)
    state = main.get_workspace(case.id, db).workflow_state

    assert state.versions.model_dump() == {
        "material_version": 1,
        "fact_version": 1,
        "issue_version": 1,
        "analysis_version": 1,
        "report_version": 1,
    }
    assert state.report_status == "REPORT_PUBLISHED"
    assert state.report_current is True
    assert state.blockers == []
    assert report.report_version == case.report_version
    assert case.report_digest


def test_report_lifecycle_statuses_cover_pending_draft_and_published(db: Session) -> None:
    case, _, report = build_report_draft(db)

    draft = compute_workflow_state(db, case)
    assert draft.report_status == "REPORT_DRAFT_EXISTS"
    assert draft.report_current is False

    report.review_status = "待复核"
    db.commit()
    pending = compute_workflow_state(db, case)
    assert pending.report_status == "REPORT_PENDING_REVIEW"
    assert pending.report_current is False
    with pytest.raises(HTTPException) as exc_info:
        publish_report(db, case, report, operation_id="pending-report")
    assert exc_info.value.status_code == 409

    report.review_status = "已接受"
    db.commit()
    publish_report(db, case, report)
    published = compute_workflow_state(db, case)
    assert published.report_status == "REPORT_PUBLISHED"
    assert published.report_current is True


def test_report_draft_cannot_complete_workflow(db: Session) -> None:
    case, _, _ = build_report_draft(db)

    state = compute_workflow_state(db, case)

    assert state.report_status == "REPORT_DRAFT_EXISTS"
    assert state.report_current is False
    assert state.next_action is not None
    assert state.next_action.code == "REPORT_STALE"
    assert "report" not in state.completed_steps


def test_report_publish_api_is_idempotent(db: Session) -> None:
    case, _, report = build_report_draft(db)

    first = publish_report(db, case, report)
    repeated = publish_report(db, case, report)
    db.refresh(case)

    assert first.replayed is False
    assert repeated == first.model_copy(update={"replayed": True})
    assert case.report_version == 1
    assert db.query(models.WorkflowEvent).filter_by(
        case_id=case.id,
        event_type="REPORT_VERSION_PUBLISHED",
    ).count() == 1


def test_report_publish_api_rejects_stale_analysis_digest(db: Session) -> None:
    case, _, report = build_report_draft(db)
    snapshot = json.loads(report.input_snapshot_json)
    snapshot["analysis_digest"] = "0" * 64
    report.input_snapshot_json = json.dumps(snapshot)
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        publish_report(db, case, report, operation_id="stale-report-digest")

    assert exc_info.value.status_code == 409
    assert "digest" in str(exc_info.value.detail)
    db.refresh(case)
    assert case.report_version == 0
    assert case.report_digest is None


def test_report_publish_api_rolls_back_all_lineage_changes(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case, _, report = build_report_draft(db)

    def fail_commit() -> None:
        raise RuntimeError("simulated report publish commit failure")

    monkeypatch.setattr(db, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="simulated report publish commit failure"):
        publish_report(db, case, report, operation_id="chain-report-rollback")

    db.expire_all()
    stored_case = db.get(models.Case, case.id)
    stored_report = db.get(models.AIOutput, report.id)
    assert stored_case is not None and stored_case.report_version == 0
    assert stored_case.report_digest is None
    assert stored_report is not None and stored_report.report_version == 0
    assert db.query(models.WorkflowEvent).filter_by(
        case_id=case.id,
        event_type="REPORT_VERSION_PUBLISHED",
    ).count() == 0


def test_analysis_update_makes_published_report_stale(db: Session) -> None:
    case, analysis, report = build_report_draft(db)
    publish_report(db, case, report)
    unit = db.get(models.WorkUnit, analysis.work_unit_id)
    replacement = models.AIOutput(
        case_id=case.id,
        work_unit_id=unit.id,
        output_type="legal_analysis",
        title=analysis.title,
        content="正式分析正文 V2",
        review_status="已接受",
        version=2,
        material_version=case.material_version,
        fact_version=case.fact_version,
        issue_version=case.issue_version,
        analysis_version=0,
    )
    db.add(replacement)
    db.commit()
    db.refresh(replacement)
    main.publish_analyses(
        case.id,
        schemas.AnalysisPublishRequest(
            analysis_ids=[replacement.id],
            operation_id="chain-analysis-update",
            reason="发布更新分析",
        ),
        db,
    )
    db.refresh(case)

    state = compute_workflow_state(db, case)

    assert case.analysis_version == 2
    assert state.report_status == "REPORT_PUBLISHED"
    assert state.report_current is False
    assert state.next_action is not None
    assert state.next_action.code == "REPORT_STALE"


def test_material_change_invalidates_the_published_chain(db: Session) -> None:
    case, _, report = build_report_draft(db)
    publish_report(db, case, report)
    advance_material_version(
        db,
        case.id,
        reason="补充新材料",
        source="final_chain_test",
        operation_id="chain-material-update",
    )
    db.commit()
    db.refresh(case)

    state = compute_workflow_state(db, case)
    stale_types = {item.entity_type for item in state.stale_outputs}
    blocker_codes = {item.code for item in state.blockers}

    assert case.material_version == 2
    assert state.current_step == "fact_review"
    assert state.report_current is False
    assert "FACTS_STALE" in blocker_codes
    assert "ANALYSIS_STALE" in blocker_codes
    assert "REPORT_STALE" in blocker_codes
    assert {"fact", "analysis", "report"} <= stale_types
    assert state.available_steps == ["case_input", "materials", "fact_review"]
