from __future__ import annotations

import json
import logging
from typing import Union

from sqlalchemy.orm import Session

from ... import models
from ...schemas import WorkflowStateSchema
from .constants import ANALYSIS_APPROVED_STATUSES, FACT_REVIEWED_STATUSES, ISSUE_REVIEWED_STATUSES


LOGGER = logging.getLogger(__name__)

LEGACY_STATE_FIELDS = (
    "facts_confirmed",
    "issues_confirmed",
    "approved_analysis_count",
    "analysis_count",
    "report_ready",
    "report_current",
)

LegacyStateValue = Union[bool, int]
LegacyWorkflowState = dict[str, LegacyStateValue]


def _analysis_ids(snapshot: str) -> set[int]:
    try:
        value = json.loads(snapshot or "{}")
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


def compute_legacy_workflow_state(db: Session, case: models.Case) -> LegacyWorkflowState:
    """Reproduce the legacy aggregate fields without reconciliation writes."""
    if case.workflow_mode != "ai_case":
        return {
            "facts_confirmed": False,
            "issues_confirmed": False,
            "approved_analysis_count": 0,
            "analysis_count": 0,
            "report_ready": False,
            "report_current": False,
        }

    with db.no_autoflush:
        facts = db.query(models.CaseFact).filter(
            models.CaseFact.case_id == case.id,
            models.CaseFact.fact_version == case.fact_version,
        ).all()
        issues = db.query(models.CaseIssue).filter(
            models.CaseIssue.case_id == case.id,
            models.CaseIssue.issue_version == case.issue_version,
        ).all()
        facts_confirmed = bool(facts) and all(
            fact.status in FACT_REVIEWED_STATUSES for fact in facts
        ) and any(fact.status == "已确认" for fact in facts)
        issues_confirmed = bool(issues) and all(
            issue.status in ISSUE_REVIEWED_STATUSES for issue in issues
        )
        confirmed_issue_ids = {
            issue.id for issue in issues if issue.status in ISSUE_REVIEWED_STATUSES
        }
        units = db.query(models.WorkUnit).filter(
            models.WorkUnit.case_id == case.id,
            models.WorkUnit.code.like("legal_analysis:%"),
        ).all()
        outputs: list[models.AIOutput] = []
        for unit in units:
            if unit.parent_issue_id not in confirmed_issue_ids:
                continue
            output = db.query(models.AIOutput).filter(
                models.AIOutput.work_unit_id == unit.id,
                models.AIOutput.output_type == "legal_analysis",
                models.AIOutput.fact_version == case.fact_version,
                models.AIOutput.issue_version == case.issue_version,
            ).order_by(models.AIOutput.version.desc(), models.AIOutput.id.desc()).first()
            if output:
                outputs.append(output)

        approved_ids = {
            output.id for output in outputs if output.review_status in ANALYSIS_APPROVED_STATUSES
        }
        report = db.query(models.AIOutput).filter(
            models.AIOutput.case_id == case.id,
            models.AIOutput.output_type == "legal_report",
            models.AIOutput.fact_version == case.fact_version,
            models.AIOutput.issue_version == case.issue_version,
        ).order_by(models.AIOutput.version.desc(), models.AIOutput.id.desc()).first()
        report_current = bool(report and approved_ids and _analysis_ids(report.input_snapshot_json) == approved_ids)

    return {
        "facts_confirmed": facts_confirmed,
        "issues_confirmed": issues_confirmed,
        "approved_analysis_count": len(approved_ids),
        "analysis_count": len(outputs),
        "report_ready": facts_confirmed and issues_confirmed and bool(approved_ids),
        "report_current": report_current,
    }


def compare_and_log_workflow_states(
    case_id: int,
    old_state: LegacyWorkflowState,
    new_state: WorkflowStateSchema,
) -> dict[str, dict[str, LegacyStateValue]]:
    new_values = {
        field: getattr(new_state, field)
        for field in LEGACY_STATE_FIELDS
    }
    differences = {
        field: {"old": old_state[field], "new": new_values[field]}
        for field in LEGACY_STATE_FIELDS
        if old_state[field] != new_values[field]
    }
    if differences:
        LOGGER.warning(
            "workflow_state_comparison_mismatch case_id=%s differences=%s",
            case_id,
            differences,
        )
    else:
        LOGGER.debug("workflow_state_comparison_match case_id=%s", case_id)
    return differences
