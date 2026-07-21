from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from ... import models
from ...utils import from_json, to_json
from .analysis import compute_analysis_digest
from .common import (
    ConcurrentVersionUpdateError,
    advance_locked_version,
    lock_case,
)


REPORT_VERSION_EVENT = "REPORT_VERSION_PUBLISHED"


@dataclass(frozen=True)
class ReportVersionPublishResult:
    case_id: int
    report_id: int
    old_version: int
    new_version: int
    report_digest: str
    analysis_version: int
    analysis_digest: str
    analysis_ids: tuple[int, ...]
    replayed: bool = False


def _normalized_analysis_ids(analysis_ids: Iterable[int]) -> tuple[int, ...]:
    normalized = tuple(sorted({int(analysis_id) for analysis_id in analysis_ids}))
    if not normalized:
        raise ValueError("A report must reference at least one published analysis")
    return normalized


def compute_report_digest(
    report_content: str,
    *,
    analysis_version: int,
    analysis_digest: str,
    analysis_ids: Iterable[int],
) -> str:
    normalized_ids = _normalized_analysis_ids(analysis_ids)
    canonical = json.dumps(
        {
            "report_content_sha256": hashlib.sha256(
                report_content.encode("utf-8")
            ).hexdigest(),
            "analysis_version": int(analysis_version),
            "analysis_digest": analysis_digest,
            "analysis_ids": list(normalized_ids),
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _report_snapshot(report: models.AIOutput) -> tuple[int, str, tuple[int, ...]]:
    snapshot = from_json(report.input_snapshot_json, {})
    try:
        analysis_version = int(snapshot.get("analysis_version", 0))
    except (TypeError, ValueError) as error:
        raise ValueError("Report analysis_version is invalid") from error
    analysis_digest = str(snapshot.get("analysis_digest") or "")
    analysis_ids = _normalized_analysis_ids(snapshot.get("analysis_ids", []))
    if analysis_version <= 0 or not analysis_digest:
        raise ValueError("Report is not bound to a published analysis version")
    return analysis_version, analysis_digest, analysis_ids


def publish_report_version(
    db: Session,
    case_id: int,
    *,
    report_id: int,
    reason: str,
    source: str,
    operation_id: Optional[str] = None,
) -> ReportVersionPublishResult:
    """Publish one report inside the caller's active transaction."""
    case = lock_case(db, case_id)
    report = db.query(models.AIOutput).filter(
        models.AIOutput.id == report_id,
        models.AIOutput.case_id == case.id,
        models.AIOutput.output_type == "legal_report",
    ).first()
    if not report:
        raise ValueError(f"Report {report_id} does not belong to case {case.id}")
    if report.review_status not in {"已接受", "已修改"}:
        raise ConcurrentVersionUpdateError(
            f"Report {report.id} has not completed review"
        )

    analysis_version, analysis_digest, analysis_ids = _report_snapshot(report)
    if case.analysis_version <= 0 or analysis_version != case.analysis_version:
        raise ConcurrentVersionUpdateError(
            f"Report {report.id} is not based on the current analysis version"
        )
    if report.analysis_version != case.analysis_version:
        raise ConcurrentVersionUpdateError(
            f"Report {report.id} analysis lineage does not match case {case.id}"
        )
    analyses = db.query(models.AIOutput).filter(
        models.AIOutput.case_id == case.id,
        models.AIOutput.id.in_(analysis_ids),
        models.AIOutput.output_type == "legal_analysis",
        models.AIOutput.analysis_version == case.analysis_version,
    ).order_by(models.AIOutput.id).all()
    if tuple(output.id for output in analyses) != analysis_ids:
        raise ConcurrentVersionUpdateError(
            f"Report {report.id} references analyses outside the current published set"
        )
    current_analysis_digest = compute_analysis_digest(db, case.id, analysis_ids)
    if current_analysis_digest != analysis_digest:
        raise ConcurrentVersionUpdateError(
            f"Report {report.id} analysis digest is no longer current"
        )

    digest = compute_report_digest(
        report.content,
        analysis_version=analysis_version,
        analysis_digest=analysis_digest,
        analysis_ids=analysis_ids,
    )
    if operation_id:
        events = db.query(models.WorkflowEvent).filter(
            models.WorkflowEvent.case_id == case.id,
            models.WorkflowEvent.event_type == REPORT_VERSION_EVENT,
        ).order_by(models.WorkflowEvent.id.desc()).all()
        for event in events:
            payload = from_json(event.payload_json, {})
            if payload.get("operation_id") != operation_id:
                continue
            if int(payload.get("report_id", 0)) != report.id or payload.get("report_digest") != digest:
                raise ConcurrentVersionUpdateError(
                    f"Report operation {operation_id} was reused for a different report"
                )
            return ReportVersionPublishResult(
                case_id=case.id,
                report_id=report.id,
                old_version=int(payload["old_version"]),
                new_version=int(payload["new_version"]),
                report_digest=digest,
                analysis_version=analysis_version,
                analysis_digest=analysis_digest,
                analysis_ids=analysis_ids,
                replayed=True,
            )

    result = advance_locked_version(
        db,
        case,
        "report_version",
        extra_values={"report_digest": digest},
    )
    report.report_version = result.new_version
    event_payload = {
        "report_id": report.id,
        "old_version": result.old_version,
        "new_version": result.new_version,
        "report_digest": digest,
        "analysis_version": analysis_version,
        "analysis_digest": analysis_digest,
        "analysis_ids": list(analysis_ids),
        "reason": reason,
        "source": source,
    }
    if operation_id:
        event_payload["operation_id"] = operation_id
    db.add(models.WorkflowEvent(
        case_id=case.id,
        event_type=REPORT_VERSION_EVENT,
        message=f"报告版本已从 V{result.old_version} 发布至 V{result.new_version}",
        payload_json=to_json(event_payload),
    ))
    db.flush()
    return ReportVersionPublishResult(
        case_id=case.id,
        report_id=report.id,
        old_version=result.old_version,
        new_version=result.new_version,
        report_digest=digest,
        analysis_version=analysis_version,
        analysis_digest=analysis_digest,
        analysis_ids=analysis_ids,
    )
