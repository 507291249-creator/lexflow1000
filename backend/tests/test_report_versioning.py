from __future__ import annotations

import json

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import main, models
from app.services.versioning import (
    compute_report_digest,
    publish_analysis_version,
    publish_report_version,
)
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


def add_case(db: Session, *, analysis_version: int = 1) -> models.Case:
    case = models.Case(
        title="报告版本测试",
        claimant="甲",
        employer="乙",
        summary="案件摘要",
        raw_facts="案件原始事实",
        workflow_mode="ai_case",
        material_version=2,
        fact_version=3,
        issue_version=4,
        analysis_version=analysis_version,
        report_version=0,
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
        description="争点描述",
        status="人工确认",
        fact_version=case.fact_version,
        issue_version=case.issue_version,
    )
    db.add(issue)
    db.commit()
    return case


def add_analysis(
    db: Session,
    case: models.Case,
    *,
    content: str = "正式分析正文",
    analysis_version: int | None = None,
    output_version: int = 1,
    unit: models.WorkUnit | None = None,
) -> models.AIOutput:
    issue = db.query(models.CaseIssue).filter_by(case_id=case.id).one()
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
        content=content,
        review_status="已接受",
        version=output_version,
        material_version=case.material_version,
        fact_version=case.fact_version,
        issue_version=case.issue_version,
        analysis_version=(
            case.analysis_version
            if analysis_version is None
            else analysis_version
        ),
    )
    db.add(output)
    db.commit()
    db.refresh(output)
    return output


def generate_report(db: Session, case: models.Case) -> models.AIOutput:
    report = main.generate_legal_report(db, case)
    db.commit()
    db.refresh(report)
    return report


def publish_report(
    db: Session,
    case: models.Case,
    report: models.AIOutput,
    *,
    operation_id: str = "publish-report-001",
):
    return publish_report_version(
        db,
        case.id,
        report_id=report.id,
        reason="律师确认正式报告",
        source="report_publish_test",
        operation_id=operation_id,
    )


def test_unpublished_analysis_cannot_generate_formal_report(db: Session) -> None:
    case = add_case(db, analysis_version=0)
    add_analysis(db, case, analysis_version=0)

    with pytest.raises(HTTPException) as exc_info:
        main.generate_legal_report(db, case)

    assert exc_info.value.status_code == 409
    assert db.query(models.AIOutput).filter_by(
        case_id=case.id,
        output_type="legal_report",
    ).count() == 0


def test_generated_legal_analysis_records_current_material_lineage(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = add_case(db)
    issue = db.query(models.CaseIssue).filter_by(case_id=case.id).one()
    unit = models.WorkUnit(
        case_id=case.id,
        code=f"legal_analysis:{issue.id}",
        title=f"法律分析：{issue.title}",
        sequence=3,
        status="待处理",
        parent_issue_id=issue.id,
    )
    db.add(unit)
    db.commit()
    monkeypatch.setattr(main, "legal_analysis", lambda *_args: {
        "core_conclusion": "测试结论",
        "risk_level": "中",
        "main_reasons": ["测试理由"],
        "legal_directions": ["测试方向"],
        "counter_arguments": ["测试反方观点"],
        "uncertainties": ["测试不确定事项"],
        "evidence_needs": ["测试证据需求"],
        "next_actions": ["测试下一步"],
        "confidence": "中",
    })

    main.run_ai_legal_analysis(db, case, unit)
    output = db.get(models.AIOutput, unit.ai_output_id)

    assert output is not None
    assert output.material_version == case.material_version
    assert output.fact_version == case.fact_version
    assert output.issue_version == case.issue_version
    assert output.analysis_version == 0


def test_report_generation_uses_only_current_published_analyses(db: Session) -> None:
    case = add_case(db)
    published = add_analysis(db, case, content="正式发布分析", analysis_version=1)
    unit = db.get(models.WorkUnit, published.work_unit_id)
    draft = add_analysis(
        db,
        case,
        content="未发布分析草稿",
        analysis_version=0,
        output_version=2,
        unit=unit,
    )

    report = generate_report(db, case)
    snapshot = json.loads(report.input_snapshot_json)

    assert snapshot["analysis_ids"] == [published.id]
    assert draft.id not in snapshot["analysis_ids"]
    assert snapshot["analysis_version"] == case.analysis_version
    assert len(snapshot["analysis_digest"]) == 64
    assert "正式发布分析" in report.content
    assert "未发布分析草稿" not in report.content
    assert report.analysis_version == case.analysis_version
    assert report.report_version == 0


def test_report_digest_is_stable_and_tracks_lineage() -> None:
    first = compute_report_digest(
        "报告正文",
        analysis_version=2,
        analysis_digest="a" * 64,
        analysis_ids=[3, 1, 3],
    )
    repeated = compute_report_digest(
        "报告正文",
        analysis_version=2,
        analysis_digest="a" * 64,
        analysis_ids=[1, 3],
    )

    assert first == repeated
    assert len(first) == 64
    assert compute_report_digest(
        "修改后的报告正文",
        analysis_version=2,
        analysis_digest="a" * 64,
        analysis_ids=[1, 3],
    ) != first
    assert compute_report_digest(
        "报告正文",
        analysis_version=3,
        analysis_digest="a" * 64,
        analysis_ids=[1, 3],
    ) != first


def test_report_publish_is_idempotent_and_records_event(db: Session) -> None:
    case = add_case(db)
    add_analysis(db, case)
    report = generate_report(db, case)

    first = publish_report(db, case, report)
    db.commit()
    repeated = publish_report(db, case, report)
    db.commit()
    db.refresh(case)
    db.refresh(report)

    assert first.replayed is False
    assert repeated == first.__class__(**{**first.__dict__, "replayed": True})
    assert case.report_version == 1
    assert case.report_digest == first.report_digest
    assert report.report_version == 1
    event = db.query(models.WorkflowEvent).filter_by(
        case_id=case.id,
        event_type="REPORT_VERSION_PUBLISHED",
    ).one()
    payload = json.loads(event.payload_json)
    assert payload["report_id"] == report.id
    assert payload["report_digest"] == first.report_digest
    assert payload["analysis_version"] == case.analysis_version
    assert payload["analysis_ids"] == list(first.analysis_ids)
    assert payload["operation_id"] == "publish-report-001"


def test_report_publish_rolls_back_version_digest_output_and_event(db: Session) -> None:
    case = add_case(db)
    add_analysis(db, case)
    report = generate_report(db, case)

    publish_report(db, case, report, operation_id="rollback-report")
    db.rollback()
    db.refresh(case)
    db.refresh(report)

    assert case.report_version == 0
    assert case.report_digest is None
    assert report.report_version == 0
    assert db.query(models.WorkflowEvent).filter_by(
        case_id=case.id,
        event_type="REPORT_VERSION_PUBLISHED",
    ).count() == 0


def test_same_analysis_version_published_report_remains_current(db: Session) -> None:
    case = add_case(db)
    add_analysis(db, case)
    report = generate_report(db, case)

    draft_state = compute_workflow_state(db, case)
    assert draft_state.report_current is False
    assert draft_state.next_action is not None
    assert draft_state.next_action.code == "REPORT_STALE"

    publish_report(db, case, report)
    db.commit()
    db.refresh(case)
    published_state = compute_workflow_state(db, case)

    assert published_state.report_current is True
    assert published_state.coverage.report.current is True
    assert published_state.blockers == []
    assert published_state.next_action is None


def test_analysis_version_change_makes_published_report_stale(db: Session) -> None:
    case = add_case(db)
    original = add_analysis(db, case, output_version=1)
    report = generate_report(db, case)
    publish_report(db, case, report)
    db.commit()

    unit = db.get(models.WorkUnit, original.work_unit_id)
    replacement = add_analysis(
        db,
        case,
        content="新分析版本",
        analysis_version=0,
        output_version=2,
        unit=unit,
    )
    publish_analysis_version(
        db,
        case.id,
        analysis_ids=[replacement.id],
        reason="发布新分析集",
        source="report_stale_test",
        operation_id="new-analysis-version",
    )
    db.commit()
    db.refresh(case)

    state = compute_workflow_state(db, case)

    assert case.analysis_version == 2
    assert state.report_current is False
    assert state.next_action is not None
    assert state.next_action.code == "REPORT_STALE"
    stale = next(item for item in state.stale_outputs if item.entity_type == "report")
    assert stale.entity_id == report.id
    assert stale.stale_reason == "analysis_version_changed"
