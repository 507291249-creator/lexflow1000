from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app import models
from app.services.workflow import BlockerCode, compute_workflow_state
from app.services.workflow.steps import check_materials


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def add_case(
    db: Session,
    *,
    raw_facts: str = "案件原始事实",
    summary: str = "",
    material_version: int = 1,
    fact_version: int = 1,
    issue_version: int = 1,
) -> models.Case:
    case = models.Case(
        title="工作流状态测试",
        claimant="甲",
        employer="乙",
        raw_facts=raw_facts,
        summary=summary,
        workflow_mode="ai_case",
        material_version=material_version,
        fact_version=fact_version,
        issue_version=issue_version,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def add_document(db: Session, case: models.Case) -> models.Document:
    document = models.Document(
        case_id=case.id,
        filename="材料.txt",
        original_filename="材料.txt",
        file_type="txt",
        mime_type="text/plain",
        raw_text="案件材料",
        processing_status="ready",
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def add_fact(
    db: Session,
    case: models.Case,
    *,
    status: str = "已确认",
    material_version: int | None = None,
) -> models.CaseFact:
    fact = models.CaseFact(
        case_id=case.id,
        ai_fact="已提取事实",
        human_fact="已确认事实" if status == "已确认" else "",
        status=status,
        material_version=case.material_version if material_version is None else material_version,
        fact_version=case.fact_version,
    )
    db.add(fact)
    db.commit()
    db.refresh(fact)
    return fact


def add_issue(
    db: Session,
    case: models.Case,
    *,
    status: str = "人工确认",
    fact_version: int | None = None,
) -> models.CaseIssue:
    issue = models.CaseIssue(
        case_id=case.id,
        title="争点一",
        status=status,
        fact_version=case.fact_version if fact_version is None else fact_version,
        issue_version=case.issue_version,
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)
    return issue


def add_analysis(
    db: Session,
    case: models.Case,
    issue: models.CaseIssue,
    *,
    review_status: str = "已接受",
    material_version: int | None = None,
    fact_version: int | None = None,
    issue_version: int | None = None,
) -> tuple[models.WorkUnit, models.AIOutput]:
    unit = models.WorkUnit(
        case_id=case.id,
        code=f"legal_analysis:{issue.id}",
        title=issue.title,
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
        content="分析正文",
        review_status=review_status,
        material_version=case.material_version if material_version is None else material_version,
        fact_version=case.fact_version if fact_version is None else fact_version,
        issue_version=case.issue_version if issue_version is None else issue_version,
    )
    db.add(output)
    db.commit()
    db.refresh(unit)
    db.refresh(output)
    return unit, output


def add_report(
    db: Session,
    case: models.Case,
    analysis_ids: list[int],
) -> models.AIOutput:
    report = models.AIOutput(
        case_id=case.id,
        output_type="legal_report",
        title="法律分析报告",
        content="报告正文",
        review_status="已接受",
        material_version=case.material_version,
        fact_version=case.fact_version,
        issue_version=case.issue_version,
        input_snapshot_json=json.dumps({"analysis_ids": analysis_ids}),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def blocker_codes(state) -> list[str]:
    return [blocker.code for blocker in state.blockers]


def prepare_through_issues(db: Session, case: models.Case) -> models.CaseIssue:
    add_fact(db, case)
    return add_issue(db, case)


def test_empty_case_stops_at_case_input(db: Session) -> None:
    case = add_case(db, raw_facts="", summary="")

    state = compute_workflow_state(db, case)

    assert state.current_step == "case_input"
    assert state.completed_steps == []
    assert set(state.next_action.model_dump()) == {"code", "label", "entity_type", "entity_ids"}
    assert state.next_action.code == BlockerCode.CASE_INPUT_MISSING.value
    assert BlockerCode.MATERIALS_MISSING.value in blocker_codes(state)


def test_workflow_state_returns_multiple_ordered_blockers(db: Session) -> None:
    case = add_case(db, raw_facts="", summary="")

    state = compute_workflow_state(db, case)

    assert blocker_codes(state) == [
        BlockerCode.CASE_INPUT_MISSING.value,
        BlockerCode.MATERIALS_MISSING.value,
        BlockerCode.FACTS_MISSING.value,
        BlockerCode.ISSUES_MISSING.value,
        BlockerCode.ANALYSIS_MISSING.value,
        BlockerCode.REPORT_MISSING.value,
    ]
    assert state.current_step == "case_input"
    assert state.next_action.code == BlockerCode.CASE_INPUT_MISSING.value


def test_workflow_state_serializes_strong_nested_schemas(db: Session) -> None:
    case = add_case(db)

    state = compute_workflow_state(db, case)
    payload = state.model_dump(mode="json")

    assert payload["coverage"]["case_input"] == {"complete": True}
    assert payload["coverage"]["analysis"] == {
        "expected": 0,
        "generated": 0,
        "approved": 0,
        "stale": 0,
    }
    assert payload["next_action"] == {
        "code": BlockerCode.FACTS_MISSING.value,
        "label": "运行事实提取",
        "entity_type": "case",
        "entity_ids": [case.id],
    }


def test_blocker_code_enum_covers_phase_contract() -> None:
    assert {code.value for code in BlockerCode} == {
        "CASE_INPUT_MISSING",
        "MATERIALS_MISSING",
        "FACTS_MISSING",
        "FACTS_PENDING_REVIEW",
        "FACTS_STALE",
        "ISSUES_MISSING",
        "ISSUES_PENDING_REVIEW",
        "ISSUES_STALE",
        "ANALYSIS_MISSING",
        "ANALYSIS_INCOMPLETE",
        "ANALYSIS_STALE",
        "REPORT_MISSING",
        "REPORT_STALE",
    }


def test_materials_complete_advances_to_fact_review(db: Session) -> None:
    case = add_case(db)
    add_document(db, case)

    state = compute_workflow_state(db, case)

    assert check_materials(db, case) == []
    assert state.current_step == "fact_review"
    assert state.completed_steps == ["case_input", "materials"]


def test_facts_missing_returns_blocker(db: Session) -> None:
    case = add_case(db)

    state = compute_workflow_state(db, case)

    assert state.current_step == "fact_review"
    assert state.next_action.code == BlockerCode.FACTS_MISSING.value


def test_facts_pending_review_returns_blocker(db: Session) -> None:
    case = add_case(db)
    fact = add_fact(db, case, status="待确认")

    state = compute_workflow_state(db, case)

    assert state.current_step == "fact_review"
    blocker = next(item for item in state.blockers if item.code == BlockerCode.FACTS_PENDING_REVIEW.value)
    assert blocker.entity_ids == [fact.id]


def test_facts_stale_returns_stale_output(db: Session) -> None:
    case = add_case(db, material_version=2)
    fact = add_fact(db, case, material_version=1)

    state = compute_workflow_state(db, case)

    assert state.current_step == "fact_review"
    assert state.next_action.code == BlockerCode.FACTS_STALE.value
    stale = next(item for item in state.stale_outputs if item.entity_type == "fact")
    assert stale.entity_id == fact.id
    assert stale.input_versions == {"material_version": 1}
    assert stale.current_versions == {"material_version": 2}


def test_issues_stale_returns_stale_output(db: Session) -> None:
    case = add_case(db, fact_version=2)
    add_fact(db, case)
    issue = add_issue(db, case, fact_version=1)

    state = compute_workflow_state(db, case)

    assert state.current_step == "issue_review"
    assert state.next_action.code == BlockerCode.ISSUES_STALE.value
    stale = next(item for item in state.stale_outputs if item.entity_type == "issue")
    assert stale.entity_id == issue.id
    assert stale.stale_reason == "fact_version_changed"


def test_analysis_stale_returns_stale_output(db: Session) -> None:
    case = add_case(db, material_version=2, fact_version=2, issue_version=2)
    issue = prepare_through_issues(db, case)
    _, analysis = add_analysis(db, case, issue, material_version=1)

    state = compute_workflow_state(db, case)

    assert state.current_step == "legal_analysis"
    assert state.next_action.code == BlockerCode.ANALYSIS_STALE.value
    stale = next(item for item in state.stale_outputs if item.entity_type == "analysis")
    assert stale.entity_id == analysis.id
    assert stale.stale_reason == "material_version_changed"


def test_report_stale_when_analysis_set_changes(db: Session) -> None:
    case = add_case(db)
    issue = prepare_through_issues(db, case)
    _, analysis = add_analysis(db, case, issue)
    report = add_report(db, case, analysis_ids=[])

    state = compute_workflow_state(db, case)

    assert state.current_step == "report"
    assert state.completed_steps == [
        "case_input",
        "materials",
        "fact_review",
        "issue_review",
        "legal_analysis",
    ]
    assert state.next_action.code == BlockerCode.REPORT_STALE.value
    stale = next(item for item in state.stale_outputs if item.entity_type == "report")
    assert stale.entity_id == report.id
    assert stale.stale_reason == "analysis_set_changed"
    assert analysis.id not in json.loads(report.input_snapshot_json)["analysis_ids"]


def test_compute_workflow_state_does_not_write(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    case = add_case(db)
    issue = prepare_through_issues(db, case)
    unit, analysis = add_analysis(db, case, issue)
    add_report(db, case, analysis_ids=[analysis.id])
    original = (case.status, case.stage, unit.status)

    def forbidden_write(*_args, **_kwargs):
        raise AssertionError("workflow state computation attempted a database write")

    monkeypatch.setattr(db, "flush", forbidden_write)
    monkeypatch.setattr(db, "commit", forbidden_write)

    state = compute_workflow_state(db, case)

    assert state.blockers == []
    assert state.next_action is None
    assert state.report_current is True
    assert (case.status, case.stage, unit.status) == original
    assert list(db.new) == []
    assert list(db.dirty) == []
    assert list(db.deleted) == []
