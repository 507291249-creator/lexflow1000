from __future__ import annotations

import json
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from ... import models
from ...schemas import StaleOutputSchema
from ...utils import from_json
from ..versioning import compute_analysis_digest, compute_report_digest
from .constants import ANALYSIS_APPROVED_STATUSES, ISSUE_REVIEWED_STATUSES


def current_facts(db: Session, case: models.Case) -> list[models.CaseFact]:
    with db.no_autoflush:
        return db.query(models.CaseFact).filter(
            models.CaseFact.case_id == case.id,
            models.CaseFact.fact_version == case.fact_version,
        ).order_by(models.CaseFact.id).all()


def current_issues(db: Session, case: models.Case) -> list[models.CaseIssue]:
    with db.no_autoflush:
        return db.query(models.CaseIssue).filter(
            models.CaseIssue.case_id == case.id,
            models.CaseIssue.issue_version == case.issue_version,
        ).order_by(models.CaseIssue.id).all()


def latest_analysis_outputs(
    db: Session,
    case: models.Case,
    issue_ids: Optional[Iterable[int]] = None,
) -> dict[int, models.AIOutput]:
    selected_issue_ids = set(issue_ids) if issue_ids is not None else {
        issue.id for issue in current_issues(db, case)
    }
    if not selected_issue_ids:
        return {}

    with db.no_autoflush:
        units = db.query(models.WorkUnit).filter(
            models.WorkUnit.case_id == case.id,
            models.WorkUnit.code.like("legal_analysis:%"),
            models.WorkUnit.parent_issue_id.in_(selected_issue_ids),
        ).all()
        unit_to_issue = {
            unit.id: unit.parent_issue_id
            for unit in units
            if unit.parent_issue_id is not None
        }
        if not unit_to_issue:
            return {}
        output_query = db.query(models.AIOutput).filter(
            models.AIOutput.case_id == case.id,
            models.AIOutput.output_type == "legal_analysis",
            models.AIOutput.work_unit_id.in_(unit_to_issue),
        )
        if case.analysis_version > 0:
            output_query = output_query.filter(
                models.AIOutput.analysis_version == case.analysis_version
            )
        outputs = output_query.all()

    latest: dict[int, models.AIOutput] = {}
    for output in outputs:
        issue_id = unit_to_issue.get(output.work_unit_id)
        if issue_id is None:
            continue
        previous = latest.get(issue_id)
        output_order = (output.version or 0, output.id or 0)
        previous_order = (previous.version or 0, previous.id or 0) if previous else (-1, -1)
        if output_order > previous_order:
            latest[issue_id] = output
    return latest


def latest_report(db: Session, case: models.Case) -> Optional[models.AIOutput]:
    with db.no_autoflush:
        query = db.query(models.AIOutput).filter(
            models.AIOutput.case_id == case.id,
            models.AIOutput.output_type == "legal_report",
        )
        if case.report_version > 0:
            query = query.filter(
                models.AIOutput.report_version == case.report_version
            )
        return query.order_by(
            models.AIOutput.version.desc(),
            models.AIOutput.id.desc(),
        ).first()


def latest_report_candidate(db: Session, case: models.Case) -> Optional[models.AIOutput]:
    with db.no_autoflush:
        return db.query(models.AIOutput).filter(
            models.AIOutput.case_id == case.id,
            models.AIOutput.output_type == "legal_report",
        ).order_by(
            models.AIOutput.version.desc(),
            models.AIOutput.id.desc(),
        ).first()


def fact_is_stale(fact: models.CaseFact, case: models.Case) -> bool:
    return fact.material_version != case.material_version


def issue_is_stale(issue: models.CaseIssue, case: models.Case) -> bool:
    return issue.fact_version != case.fact_version


def analysis_is_stale(output: models.AIOutput, case: models.Case) -> bool:
    return (
        output.material_version != case.material_version
        or output.fact_version != case.fact_version
        or output.issue_version != case.issue_version
    )


def _snapshot_analysis_ids(output: models.AIOutput) -> set[int]:
    value = output.input_snapshot_json
    if isinstance(value, str):
        try:
            value = json.loads(value or "{}")
        except (TypeError, ValueError):
            return set()
    if not isinstance(value, dict):
        return set()

    normalized: set[int] = set()
    for item in value.get("analysis_ids", []):
        try:
            normalized.add(int(item))
        except (TypeError, ValueError):
            continue
    return normalized


def _report_lineage_snapshot(report: models.AIOutput) -> tuple[int, str, set[int]]:
    value = from_json(report.input_snapshot_json, {}) if isinstance(
        report.input_snapshot_json, str
    ) else report.input_snapshot_json
    if not isinstance(value, dict):
        return 0, "", set()
    try:
        analysis_version = int(value.get("analysis_version", 0))
    except (TypeError, ValueError):
        analysis_version = 0
    return (
        analysis_version,
        str(value.get("analysis_digest") or ""),
        _snapshot_analysis_ids(report),
    )


def report_is_stale(
    report: models.AIOutput,
    case: models.Case,
    current_analysis_ids: set[int],
    current_analysis_digest: Optional[str] = None,
) -> bool:
    versions_stale = analysis_is_stale(report, case)
    snapshot_analysis_version, snapshot_analysis_digest, snapshot_ids = (
        _report_lineage_snapshot(report)
    )
    analysis_set_stale = snapshot_ids != current_analysis_ids
    has_report_lineage = bool(
        report.analysis_version > 0
        or snapshot_analysis_version > 0
        or snapshot_analysis_digest
        or case.report_version > 0
    )
    if not has_report_lineage:
        return versions_stale or analysis_set_stale
    if not current_analysis_digest:
        return True
    try:
        expected_report_digest = compute_report_digest(
            report.content,
            analysis_version=snapshot_analysis_version,
            analysis_digest=snapshot_analysis_digest,
            analysis_ids=snapshot_ids,
        )
    except ValueError:
        return True
    return bool(
        versions_stale
        or analysis_set_stale
        or report.review_status not in {"已接受", "已修改"}
        or report.analysis_version != case.analysis_version
        or snapshot_analysis_version != case.analysis_version
        or snapshot_analysis_digest != current_analysis_digest
        or report.report_version <= 0
        or report.report_version != case.report_version
        or case.report_digest != expected_report_digest
    )


def current_valid_analyses(db: Session, case: models.Case) -> dict[int, models.AIOutput]:
    issues = [
        issue
        for issue in current_issues(db, case)
        if issue.status in ISSUE_REVIEWED_STATUSES and not issue_is_stale(issue, case)
    ]
    latest = latest_analysis_outputs(db, case, (issue.id for issue in issues))
    return {
        issue_id: output
        for issue_id, output in latest.items()
        if not analysis_is_stale(output, case)
        and output.review_status in ANALYSIS_APPROVED_STATUSES
    }


def current_analysis_lineage(
    db: Session,
    case: models.Case,
) -> tuple[set[int], Optional[str]]:
    analysis_ids = {
        output.id for output in current_valid_analyses(db, case).values()
    }
    if not analysis_ids:
        return analysis_ids, None
    try:
        return analysis_ids, compute_analysis_digest(db, case.id, analysis_ids)
    except ValueError:
        return analysis_ids, None


def _version_reason(input_versions: dict[str, int], current_versions: dict[str, int]) -> str:
    changed = [name for name, version in input_versions.items() if version != current_versions[name]]
    return f"{changed[0]}_changed" if len(changed) == 1 else "input_versions_changed"


def stale_fact_output(fact: models.CaseFact, case: models.Case) -> Optional[StaleOutputSchema]:
    if not fact_is_stale(fact, case):
        return None
    return StaleOutputSchema(
        entity_type="fact",
        entity_id=fact.id,
        title=(fact.human_fact or fact.ai_fact or f"事实 #{fact.id}")[:255],
        review_status=fact.status,
        is_stale=True,
        stale_reason="material_version_changed",
        stale_at=None,
        input_versions={"material_version": fact.material_version},
        current_versions={"material_version": case.material_version},
        required_action="rerun_fact_extraction",
    )


def stale_issue_output(issue: models.CaseIssue, case: models.Case) -> Optional[StaleOutputSchema]:
    if not issue_is_stale(issue, case):
        return None
    return StaleOutputSchema(
        entity_type="issue",
        entity_id=issue.id,
        title=issue.title,
        review_status=issue.status,
        is_stale=True,
        stale_reason="fact_version_changed",
        stale_at=None,
        input_versions={"fact_version": issue.fact_version},
        current_versions={"fact_version": case.fact_version},
        required_action="rerun_issue_identification",
    )


def stale_analysis_output(
    output: models.AIOutput,
    case: models.Case,
) -> Optional[StaleOutputSchema]:
    if not analysis_is_stale(output, case):
        return None
    input_versions = {
        "material_version": output.material_version,
        "fact_version": output.fact_version,
        "issue_version": output.issue_version,
    }
    current_versions = {
        "material_version": case.material_version,
        "fact_version": case.fact_version,
        "issue_version": case.issue_version,
    }
    return StaleOutputSchema(
        entity_type="analysis",
        entity_id=output.id,
        title=output.title,
        review_status=output.review_status,
        is_stale=True,
        stale_reason=_version_reason(input_versions, current_versions),
        stale_at=None,
        input_versions=input_versions,
        current_versions=current_versions,
        required_action="rerun_legal_analysis",
    )


def stale_report_output(
    report: models.AIOutput,
    case: models.Case,
    current_analysis_ids: set[int],
    current_analysis_digest: Optional[str] = None,
) -> Optional[StaleOutputSchema]:
    versions_stale = analysis_is_stale(report, case)
    snapshot_analysis_version, snapshot_analysis_digest, snapshot_ids = (
        _report_lineage_snapshot(report)
    )
    analysis_set_stale = snapshot_ids != current_analysis_ids
    analysis_version_stale = bool(
        snapshot_analysis_version
        and (
            snapshot_analysis_version != case.analysis_version
            or report.analysis_version != case.analysis_version
        )
    )
    analysis_digest_stale = bool(
        snapshot_analysis_digest
        and snapshot_analysis_digest != current_analysis_digest
    )
    report_version_stale = bool(
        report.analysis_version > 0
        and (
            report.report_version <= 0
            or report.report_version != case.report_version
        )
    )
    report_pending_review = bool(
        report.analysis_version > 0
        and report.review_status not in {"已接受", "已修改"}
    )
    report_digest_stale = False
    if snapshot_analysis_version > 0 and snapshot_analysis_digest and snapshot_ids:
        expected_digest = compute_report_digest(
            report.content,
            analysis_version=snapshot_analysis_version,
            analysis_digest=snapshot_analysis_digest,
            analysis_ids=snapshot_ids,
        )
        report_digest_stale = case.report_digest != expected_digest
    if not report_is_stale(
        report,
        case,
        current_analysis_ids,
        current_analysis_digest,
    ):
        return None

    input_versions = {
        "material_version": report.material_version,
        "fact_version": report.fact_version,
        "issue_version": report.issue_version,
        "analysis_version": report.analysis_version,
        "report_version": report.report_version,
    }
    current_versions = {
        "material_version": case.material_version,
        "fact_version": case.fact_version,
        "issue_version": case.issue_version,
        "analysis_version": case.analysis_version,
        "report_version": case.report_version,
    }
    if report_pending_review:
        reason = "report_pending_review"
    elif report_version_stale:
        reason = "report_version_changed"
    elif report_digest_stale:
        reason = "report_digest_changed"
    elif analysis_version_stale:
        reason = "analysis_version_changed"
    elif analysis_digest_stale:
        reason = "analysis_digest_changed"
    elif versions_stale and analysis_set_stale:
        reason = "input_versions_and_analysis_set_changed"
    elif analysis_set_stale:
        reason = "analysis_set_changed"
    else:
        reason = _version_reason(input_versions, current_versions)
    return StaleOutputSchema(
        entity_type="report",
        entity_id=report.id,
        title=report.title,
        review_status=report.review_status,
        is_stale=True,
        stale_reason=reason,
        stale_at=None,
        input_versions=input_versions,
        current_versions=current_versions,
        required_action="regenerate_report",
    )


def collect_stale_outputs(db: Session, case: models.Case) -> list[StaleOutputSchema]:
    stale_outputs: list[StaleOutputSchema] = []
    for fact in current_facts(db, case):
        stale = stale_fact_output(fact, case)
        if stale:
            stale_outputs.append(stale)
    issues = current_issues(db, case)
    for issue in issues:
        stale = stale_issue_output(issue, case)
        if stale:
            stale_outputs.append(stale)
    for output in latest_analysis_outputs(db, case, (issue.id for issue in issues)).values():
        stale = stale_analysis_output(output, case)
        if stale:
            stale_outputs.append(stale)
    report = latest_report(db, case)
    if report:
        valid_analysis_ids, analysis_digest = current_analysis_lineage(db, case)
        stale = stale_report_output(
            report,
            case,
            valid_analysis_ids,
            analysis_digest,
        )
        if stale:
            stale_outputs.append(stale)
    return stale_outputs
