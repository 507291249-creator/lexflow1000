from __future__ import annotations

import ast
import json
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import main, models, schemas
from app.services.workflow import (
    compare_and_log_workflow_states,
    compute_legacy_workflow_state,
    compute_workflow_state,
)


LEGACY_FIELDS = {
    "facts_confirmed",
    "issues_confirmed",
    "approved_analysis_count",
    "analysis_count",
    "report_ready",
    "report_current",
}


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
        title="Workspace 状态测试",
        claimant="甲",
        employer="乙",
        raw_facts="案件原始事实",
        workflow_mode="ai_case",
        material_version=1,
        fact_version=1,
        issue_version=1,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def add_complete_workflow(
    db: Session,
    case: models.Case,
    *,
    analysis_material_version: int = 1,
    include_report: bool = True,
) -> dict[str, object]:
    fact_unit = models.WorkUnit(
        case_id=case.id,
        code="fact_extraction",
        title="事实提取",
        sequence=1,
        status="待处理",
    )
    issue_unit = models.WorkUnit(
        case_id=case.id,
        code="issue_identification",
        title="争点识别",
        sequence=2,
        status="待处理",
    )
    db.add_all([fact_unit, issue_unit])
    db.flush()
    fact = models.CaseFact(
        case_id=case.id,
        work_unit_id=fact_unit.id,
        ai_fact="AI 事实",
        human_fact="已确认事实",
        status="已确认",
        material_version=case.material_version,
        fact_version=case.fact_version,
    )
    issue = models.CaseIssue(
        case_id=case.id,
        work_unit_id=issue_unit.id,
        title="争点一",
        status="人工确认",
        fact_version=case.fact_version,
        issue_version=case.issue_version,
    )
    db.add_all([fact, issue])
    db.flush()
    analysis_unit = models.WorkUnit(
        case_id=case.id,
        code=f"legal_analysis:{issue.id}",
        title="争点一分析",
        sequence=3,
        status="待人工复核",
        parent_issue_id=issue.id,
    )
    db.add(analysis_unit)
    db.flush()
    analysis = models.AIOutput(
        case_id=case.id,
        work_unit_id=analysis_unit.id,
        output_type="legal_analysis",
        title="法律分析：争点一",
        content="分析正文",
        review_status="已接受",
        material_version=analysis_material_version,
        fact_version=case.fact_version,
        issue_version=case.issue_version,
    )
    db.add(analysis)
    db.flush()

    report_unit = None
    report = None
    if include_report:
        report_unit = models.WorkUnit(
            case_id=case.id,
            code="legal_analysis_report",
            title="法律分析报告",
            sequence=4,
            status="待处理",
        )
        db.add(report_unit)
        db.flush()
        report = models.AIOutput(
            case_id=case.id,
            work_unit_id=report_unit.id,
            output_type="legal_report",
            title="法律分析报告",
            content="报告正文",
            review_status="已接受",
            material_version=case.material_version,
            fact_version=case.fact_version,
            issue_version=case.issue_version,
            input_snapshot_json=json.dumps({"analysis_ids": [analysis.id]}),
        )
        db.add(report)

    db.commit()
    return {
        "fact_unit": fact_unit,
        "issue_unit": issue_unit,
        "analysis_unit": analysis_unit,
        "report_unit": report_unit,
        "analysis": analysis,
        "report": report,
    }


def test_workspace_returns_workflow_state(db: Session) -> None:
    case = add_case(db)

    def override_db():
        yield db

    main.app.dependency_overrides[main.get_db] = override_db
    try:
        response = TestClient(main.app).get(f"/cases/{case.id}/workspace")
    finally:
        main.app.dependency_overrides.clear()
    assert response.status_code == 200
    state = response.json()["workflow_state"]

    assert state["current_step"] == "fact_review"
    assert state["next_action"] == {
        "code": "FACTS_MISSING",
        "label": "运行事实提取",
        "entity_type": "case",
        "entity_ids": [case.id],
    }
    assert state["coverage"]["facts"] == {
        "total": 0,
        "reviewed": 0,
        "confirmed": 0,
        "stale": 0,
    }
    schemas.WorkspaceSchema.model_validate(response.json())
    route = next(route for route in main.app.routes if getattr(route, "path", None) == "/cases/{case_id}/workspace")
    assert route.response_model is schemas.WorkspaceSchema


def test_workspace_get_does_not_write_database(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = add_case(db)
    records = add_complete_workflow(db, case)
    units = [
        records["fact_unit"],
        records["issue_unit"],
        records["analysis_unit"],
        records["report_unit"],
    ]
    original_case = (case.status, case.stage)
    original_unit_statuses = [unit.status for unit in units]

    def forbidden_write(*_args, **_kwargs):
        raise AssertionError("workspace GET attempted a database write")

    monkeypatch.setattr(db, "add", forbidden_write)
    monkeypatch.setattr(db, "delete", forbidden_write)
    monkeypatch.setattr(db, "flush", forbidden_write)
    monkeypatch.setattr(db, "commit", forbidden_write)

    response = main.get_workspace(case.id, db)

    assert response.workflow_state.report_current is True
    assert (case.status, case.stage) == original_case
    assert [unit.status for unit in units] == original_unit_statuses
    assert list(db.new) == []
    assert list(db.dirty) == []
    assert list(db.deleted) == []


def test_workspace_preserves_legacy_fields(db: Session) -> None:
    case = add_case(db)
    add_complete_workflow(db, case)

    state = main.get_workspace(case.id, db).workflow_state

    assert LEGACY_FIELDS <= state.model_dump().keys()
    assert state.facts_confirmed is True
    assert state.issues_confirmed is True
    assert state.analysis_count == 1
    assert state.approved_analysis_count == 1
    assert state.report_ready is True
    assert state.report_current is True


def test_old_and_new_state_match_for_current_workflow(
    db: Session,
    caplog: pytest.LogCaptureFixture,
) -> None:
    case = add_case(db)
    add_complete_workflow(db, case)
    old_state = compute_legacy_workflow_state(db, case)
    new_state = compute_workflow_state(db, case)

    with caplog.at_level(logging.DEBUG, logger="app.services.workflow.legacy"):
        differences = compare_and_log_workflow_states(case.id, old_state, new_state)

    assert differences == {}
    assert "workflow_state_comparison_match" in caplog.text


def test_workspace_returns_stale_analysis_and_logs_difference(
    db: Session,
    caplog: pytest.LogCaptureFixture,
) -> None:
    case = add_case(db)
    records = add_complete_workflow(
        db,
        case,
        analysis_material_version=0,
        include_report=False,
    )

    with caplog.at_level(logging.WARNING, logger="app.services.workflow.legacy"):
        state = main.get_workspace(case.id, db).workflow_state

    stale = next(item for item in state.stale_outputs if item.entity_type == "analysis")
    assert state.current_step == "legal_analysis"
    assert state.next_action.code == "ANALYSIS_STALE"
    assert stale.entity_id == records["analysis"].id
    assert stale.stale_reason == "material_version_changed"
    assert "workflow_state_comparison_mismatch" in caplog.text


def test_get_route_write_audit_has_no_known_write_routes() -> None:
    tree = ast.parse(Path(main.__file__).read_text())
    findings: dict[str, set[str]] = {}
    for function in tree.body:
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        is_get = any(
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr == "get"
            for decorator in function.decorator_list
        )
        if not is_get:
            continue
        operations: set[str] = set()
        for node in ast.walk(function):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in {
                    "ensure_case_workflow",
                    "reconcile_ai_case_workflow",
                }:
                    operations.add(node.func.id)
                if isinstance(node.func, ast.Attribute) and node.func.attr in {"commit", "flush"}:
                    operations.add(node.func.attr)
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Attribute) and target.attr in {"status", "stage"}:
                        operations.add(f"assign:{target.attr}")
        if operations:
            findings[function.name] = operations

    assert findings == {}


def test_work_units_get_only_returns_existing_units(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = add_case(db)
    records = add_complete_workflow(db, case)
    units = [
        records["fact_unit"],
        records["issue_unit"],
        records["analysis_unit"],
        records["report_unit"],
    ]
    case_id = case.id
    unit_ids = [unit.id for unit in units]
    original_statuses = [unit.status for unit in units]

    def forbidden_write(*_args, **_kwargs):
        raise AssertionError("work-units GET attempted a database write")

    monkeypatch.setattr(db, "add", forbidden_write)
    monkeypatch.setattr(db, "delete", forbidden_write)
    monkeypatch.setattr(db, "flush", forbidden_write)
    monkeypatch.setattr(db, "commit", forbidden_write)

    response = main.list_work_units(case_id, db)

    assert [item["id"] for item in response] == unit_ids
    assert [unit.status for unit in units] == original_statuses
    assert list(db.new) == []
    assert list(db.dirty) == []
    assert list(db.deleted) == []
