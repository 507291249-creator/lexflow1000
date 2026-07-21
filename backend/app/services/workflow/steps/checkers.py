from __future__ import annotations

from sqlalchemy.orm import Session

from .... import models
from ....schemas import BlockerSchema
from ..blockers import make_blocker
from ..constants import (
    ANALYSIS_APPROVED_STATUSES,
    FACT_REVIEWED_STATUSES,
    ISSUE_REVIEWED_STATUSES,
    BlockerCode,
)
from ..stale import (
    analysis_is_stale,
    current_analysis_lineage,
    current_facts,
    current_issues,
    current_valid_analyses,
    fact_is_stale,
    issue_is_stale,
    latest_analysis_outputs,
    latest_report,
    report_is_stale,
)


def check_case_input(db: Session, case: models.Case) -> list[BlockerSchema]:
    del db
    if (case.raw_facts or "").strip() or (case.summary or "").strip():
        return []
    return [make_blocker(
        BlockerCode.CASE_INPUT_MISSING,
        "case_input",
        "案件尚未提供可用于工作流计算的事实输入。",
        entity_type="case",
        entity_ids=[case.id],
    )]


def check_materials(db: Session, case: models.Case) -> list[BlockerSchema]:
    with db.no_autoflush:
        documents = db.query(models.Document.id).filter(models.Document.case_id == case.id).all()
    if documents or (case.raw_facts or "").strip():
        return []
    return [make_blocker(
        BlockerCode.MATERIALS_MISSING,
        "materials",
        "案件尚无上传材料或现场录入的原始事实。",
        entity_type="case",
        entity_ids=[case.id],
    )]


def check_facts(db: Session, case: models.Case) -> list[BlockerSchema]:
    facts = current_facts(db, case)
    if not facts:
        return [make_blocker(
            BlockerCode.FACTS_MISSING,
            "fact_review",
            "当前事实版本尚未生成任何事实。",
            entity_type="case",
            entity_ids=[case.id],
            details={"fact_version": case.fact_version},
        )]

    blockers: list[BlockerSchema] = []
    stale_ids = [fact.id for fact in facts if fact_is_stale(fact, case)]
    if stale_ids:
        blockers.append(make_blocker(
            BlockerCode.FACTS_STALE,
            "fact_review",
            "部分事实基于旧材料版本生成。",
            entity_type="fact",
            entity_ids=stale_ids,
            details={"material_version": case.material_version},
        ))
    pending_ids = [fact.id for fact in facts if fact.status not in FACT_REVIEWED_STATUSES]
    confirmed_ids = [fact.id for fact in facts if fact.status == "已确认"]
    if pending_ids or not confirmed_ids:
        blockers.append(make_blocker(
            BlockerCode.FACTS_PENDING_REVIEW,
            "fact_review",
            "事实尚未全部复核，或没有可进入后续流程的已确认事实。",
            entity_type="fact",
            entity_ids=pending_ids or [fact.id for fact in facts],
            details={"confirmed_count": len(confirmed_ids), "total_count": len(facts)},
        ))
    return blockers


def check_issues(db: Session, case: models.Case) -> list[BlockerSchema]:
    issues = current_issues(db, case)
    if not issues:
        return [make_blocker(
            BlockerCode.ISSUES_MISSING,
            "issue_review",
            "当前争点版本尚未生成任何争点。",
            entity_type="case",
            entity_ids=[case.id],
            details={"issue_version": case.issue_version},
        )]

    blockers: list[BlockerSchema] = []
    stale_ids = [issue.id for issue in issues if issue_is_stale(issue, case)]
    if stale_ids:
        blockers.append(make_blocker(
            BlockerCode.ISSUES_STALE,
            "issue_review",
            "部分争点基于旧事实版本生成。",
            entity_type="issue",
            entity_ids=stale_ids,
            details={"fact_version": case.fact_version},
        ))
    pending_ids = [issue.id for issue in issues if issue.status not in ISSUE_REVIEWED_STATUSES]
    if pending_ids:
        blockers.append(make_blocker(
            BlockerCode.ISSUES_PENDING_REVIEW,
            "issue_review",
            "争点尚未全部完成人工复核。",
            entity_type="issue",
            entity_ids=pending_ids,
            details={"total_count": len(issues)},
        ))
    return blockers


def check_analysis(db: Session, case: models.Case) -> list[BlockerSchema]:
    issues = [issue for issue in current_issues(db, case) if issue.status in ISSUE_REVIEWED_STATUSES]
    issue_ids = {issue.id for issue in issues}
    analyses = latest_analysis_outputs(db, case, issue_ids)
    if not analyses:
        return [make_blocker(
            BlockerCode.ANALYSIS_MISSING,
            "legal_analysis",
            "当前已确认争点尚未生成法律分析。",
            entity_type="issue",
            entity_ids=sorted(issue_ids),
        )]

    blockers: list[BlockerSchema] = []
    stale_ids = [output.id for output in analyses.values() if analysis_is_stale(output, case)]
    if stale_ids:
        blockers.append(make_blocker(
            BlockerCode.ANALYSIS_STALE,
            "legal_analysis",
            "部分法律分析的材料、事实或争点输入版本已经变化。",
            entity_type="analysis",
            entity_ids=stale_ids,
            details={
                "material_version": case.material_version,
                "fact_version": case.fact_version,
                "issue_version": case.issue_version,
            },
        ))
    missing_issue_ids = sorted(issue_ids - analyses.keys())
    if missing_issue_ids:
        blockers.append(make_blocker(
            BlockerCode.ANALYSIS_INCOMPLETE,
            "legal_analysis",
            "部分已确认争点尚未生成法律分析。",
            entity_type="issue",
            entity_ids=missing_issue_ids,
        ))
    pending_ids = [
        output.id
        for output in analyses.values()
        if not analysis_is_stale(output, case)
        and output.review_status not in ANALYSIS_APPROVED_STATUSES
    ]
    if pending_ids:
        blockers.append(make_blocker(
            BlockerCode.ANALYSIS_INCOMPLETE,
            "legal_analysis",
            "部分当前法律分析尚未完成人工复核。",
            entity_type="analysis",
            entity_ids=pending_ids,
        ))
    return blockers


def check_report(db: Session, case: models.Case) -> list[BlockerSchema]:
    report = latest_report(db, case)
    if not report:
        return [make_blocker(
            BlockerCode.REPORT_MISSING,
            "report",
            "当前工作流尚未生成法律分析报告。",
            entity_type="case",
            entity_ids=[case.id],
        )]
    analysis_ids, analysis_digest = current_analysis_lineage(db, case)
    if report_is_stale(report, case, analysis_ids, analysis_digest):
        return [make_blocker(
            BlockerCode.REPORT_STALE,
            "report",
            "报告输入版本或已批准分析集合已经变化。",
            entity_type="report",
            entity_ids=[report.id],
            details={
                "current_analysis_ids": sorted(analysis_ids),
                "analysis_version": case.analysis_version,
                "report_version": case.report_version,
            },
        )]
    return []
