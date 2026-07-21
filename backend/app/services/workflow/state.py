from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from ... import models
from ...schemas import (
    BlockerSchema,
    CoverageSchema,
    NextActionSchema,
    WorkflowStateSchema,
    WorkflowStepCode,
)
from .constants import (
    ANALYSIS_APPROVED_STATUSES,
    FACT_REVIEWED_STATUSES,
    ISSUE_REVIEWED_STATUSES,
    WORKFLOW_STEP_ORDER,
)
from .stale import (
    analysis_is_stale,
    collect_stale_outputs,
    current_analysis_lineage,
    current_facts,
    current_issues,
    current_valid_analyses,
    fact_is_stale,
    issue_is_stale,
    latest_analysis_outputs,
    latest_report,
    latest_report_candidate,
    report_is_stale,
)
from .steps import (
    check_analysis,
    check_case_input,
    check_facts,
    check_issues,
    check_materials,
    check_report,
)


StepChecker = Callable[[Session, models.Case], list[BlockerSchema]]

STEP_CHECKERS: dict[WorkflowStepCode, StepChecker] = {
    "case_input": check_case_input,
    "materials": check_materials,
    "fact_review": check_facts,
    "issue_review": check_issues,
    "legal_analysis": check_analysis,
    "report": check_report,
}


def _report_status(db: Session, case: models.Case):
    report = latest_report_candidate(db, case)
    if not report:
        return None
    if report.review_status not in ANALYSIS_APPROVED_STATUSES:
        return "REPORT_PENDING_REVIEW"
    if report.report_version <= 0:
        return "REPORT_DRAFT_EXISTS"
    return "REPORT_PUBLISHED"


def _coverage(db: Session, case: models.Case) -> CoverageSchema:
    facts = current_facts(db, case)
    issues = current_issues(db, case)
    reviewed_issues = [issue for issue in issues if issue.status in ISSUE_REVIEWED_STATUSES]
    analyses = latest_analysis_outputs(db, case, (issue.id for issue in reviewed_issues))
    valid_analyses = current_valid_analyses(db, case)
    analysis_ids, analysis_digest = current_analysis_lineage(db, case)
    report = latest_report(db, case)
    with db.no_autoflush:
        documents = db.query(models.Document).filter(models.Document.case_id == case.id).all()
    return CoverageSchema(
        case_input={
            "complete": bool((case.raw_facts or "").strip() or (case.summary or "").strip()),
        },
        materials={
            "total": len(documents),
            "ready": sum(document.processing_status == "ready" for document in documents),
            "has_inline_input": bool((case.raw_facts or "").strip()),
        },
        facts={
            "total": len(facts),
            "reviewed": sum(fact.status in FACT_REVIEWED_STATUSES for fact in facts),
            "confirmed": sum(fact.status == "已确认" for fact in facts),
            "stale": sum(fact_is_stale(fact, case) for fact in facts),
        },
        issues={
            "total": len(issues),
            "reviewed": len(reviewed_issues),
            "stale": sum(issue_is_stale(issue, case) for issue in issues),
        },
        analysis={
            "expected": len(reviewed_issues),
            "generated": len(analyses),
            "approved": len(valid_analyses),
            "stale": sum(analysis_is_stale(output, case) for output in analyses.values()),
        },
        report={
            "generated": report is not None,
            "current": bool(
                report
                and not report_is_stale(
                    report,
                    case,
                    analysis_ids,
                    analysis_digest,
                )
            ),
        },
    )


def compute_workflow_state(db: Session, case: models.Case) -> WorkflowStateSchema:
    """Compute a deterministic workflow snapshot without mutating ORM state."""
    with db.no_autoflush:
        blockers_by_step = {
            step: STEP_CHECKERS[step](db, case)
            for step in WORKFLOW_STEP_ORDER
        }
        blocking_step = next(
            (
                step
                for step in WORKFLOW_STEP_ORDER
                if any(blocker.severity == "blocking" for blocker in blockers_by_step[step])
            ),
            None,
        )
        if blocking_step is None:
            current_step: WorkflowStepCode = "report"
            completed_steps = list(WORKFLOW_STEP_ORDER)
            available_steps = list(WORKFLOW_STEP_ORDER)
        else:
            current_index = WORKFLOW_STEP_ORDER.index(blocking_step)
            current_step = blocking_step
            completed_steps = list(WORKFLOW_STEP_ORDER[:current_index])
            available_steps = list(WORKFLOW_STEP_ORDER[:current_index + 1])

        blockers = [
            blocker
            for step in WORKFLOW_STEP_ORDER
            for blocker in blockers_by_step[step]
        ]
        first_blocker = next(
            (blocker for blocker in blockers if blocker.severity == "blocking"),
            None,
        )
        next_action = None
        if first_blocker:
            next_action = NextActionSchema(
                code=first_blocker.code,
                label=first_blocker.resolution or first_blocker.message,
                entity_type=first_blocker.entity_type,
                entity_ids=first_blocker.entity_ids,
            )

        facts = current_facts(db, case)
        issues = current_issues(db, case)
        facts_confirmed = bool(facts) and all(
            fact.status in FACT_REVIEWED_STATUSES and not fact_is_stale(fact, case)
            for fact in facts
        ) and any(fact.status == "已确认" for fact in facts)
        issues_confirmed = bool(issues) and all(
            issue.status in ISSUE_REVIEWED_STATUSES and not issue_is_stale(issue, case)
            for issue in issues
        )
        reviewed_issue_ids = {
            issue.id for issue in issues if issue.status in ISSUE_REVIEWED_STATUSES
        }
        analyses = latest_analysis_outputs(db, case, reviewed_issue_ids)
        approved_analyses = [
            output
            for output in analyses.values()
            if output.review_status in ANALYSIS_APPROVED_STATUSES
            and not analysis_is_stale(output, case)
        ]
        report = latest_report(db, case)
        current_analysis_ids, current_analysis_digest = current_analysis_lineage(
            db,
            case,
        )
        report_current = bool(
            report
            and not report_is_stale(
                report,
                case,
                current_analysis_ids,
                current_analysis_digest,
            )
        )

        return WorkflowStateSchema(
            current_step=current_step,
            completed_steps=completed_steps,
            available_steps=available_steps,
            blockers=blockers,
            stale_outputs=collect_stale_outputs(db, case),
            coverage=_coverage(db, case),
            next_action=next_action,
            versions={
                "material_version": case.material_version,
                "fact_version": case.fact_version,
                "issue_version": case.issue_version,
                "analysis_version": case.analysis_version,
                "report_version": case.report_version,
            },
            report_status=_report_status(db, case),
            facts_confirmed=facts_confirmed,
            issues_confirmed=issues_confirmed,
            approved_analysis_count=len(approved_analyses),
            analysis_count=len(analyses),
            report_ready=facts_confirmed and issues_confirmed and bool(approved_analyses),
            report_current=report_current,
        )
