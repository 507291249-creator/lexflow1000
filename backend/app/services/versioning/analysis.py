from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from ... import models
from ...utils import from_json, to_json
from .common import (
    ConcurrentVersionUpdateError,
    advance_locked_version,
    lock_case,
)


ANALYSIS_VERSION_EVENT = "ANALYSIS_VERSION_PUBLISHED"


@dataclass(frozen=True)
class AnalysisVersionPublishResult:
    case_id: int
    old_version: int
    new_version: int
    analysis_digest: str
    analysis_ids: tuple[int, ...]
    replayed: bool = False


def _normalized_analysis_ids(analysis_ids: Iterable[int]) -> tuple[int, ...]:
    normalized = tuple(sorted({int(analysis_id) for analysis_id in analysis_ids}))
    if not normalized:
        raise ValueError("At least one analysis output is required for publication")
    return normalized


def _analysis_outputs(
    db: Session,
    case_id: int,
    analysis_ids: Iterable[int],
) -> tuple[tuple[int, ...], list[models.AIOutput]]:
    normalized_ids = _normalized_analysis_ids(analysis_ids)
    outputs = db.query(models.AIOutput).filter(
        models.AIOutput.case_id == case_id,
        models.AIOutput.id.in_(normalized_ids),
        models.AIOutput.output_type == "legal_analysis",
    ).order_by(models.AIOutput.id).all()
    found_ids = tuple(output.id for output in outputs)
    if found_ids != normalized_ids:
        missing = sorted(set(normalized_ids) - set(found_ids))
        raise ValueError(
            f"Analysis outputs do not belong to case {case_id} or are not legal analyses: {missing}"
        )
    return normalized_ids, outputs


def _reviewed_content(db: Session, output: models.AIOutput) -> str:
    trace = db.query(models.DecisionTrace).filter(
        models.DecisionTrace.ai_output_id == output.id,
        models.DecisionTrace.action == "修改",
    ).order_by(
        models.DecisionTrace.created_at.desc(),
        models.DecisionTrace.id.desc(),
    ).first()
    return trace.human_revision if trace and trace.human_revision else output.content


def analysis_digest_payload(
    db: Session,
    case_id: int,
    analysis_ids: Iterable[int],
) -> list[dict[str, object]]:
    _, outputs = _analysis_outputs(db, case_id, analysis_ids)
    return [
        {
            "analysis_id": output.id,
            "work_unit_id": output.work_unit_id,
            "output_version": output.version or 0,
            "review_status": output.review_status or "",
            "material_version": output.material_version or 0,
            "fact_version": output.fact_version or 0,
            "issue_version": output.issue_version or 0,
            "content_sha256": hashlib.sha256(
                _reviewed_content(db, output).encode("utf-8")
            ).hexdigest(),
        }
        for output in outputs
    ]


def compute_analysis_digest(
    db: Session,
    case_id: int,
    analysis_ids: Iterable[int],
) -> str:
    canonical = json.dumps(
        analysis_digest_payload(db, case_id, analysis_ids),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def publish_analysis_version(
    db: Session,
    case_id: int,
    *,
    analysis_ids: Iterable[int],
    reason: str,
    source: str,
    operation_id: Optional[str] = None,
) -> AnalysisVersionPublishResult:
    """Publish one analysis set inside the caller's active transaction."""
    case = lock_case(db, case_id)
    normalized_ids, outputs = _analysis_outputs(db, case.id, analysis_ids)
    digest = compute_analysis_digest(db, case.id, normalized_ids)

    if operation_id:
        events = db.query(models.WorkflowEvent).filter(
            models.WorkflowEvent.case_id == case.id,
            models.WorkflowEvent.event_type == ANALYSIS_VERSION_EVENT,
        ).order_by(models.WorkflowEvent.id.desc()).all()
        for event in events:
            payload = from_json(event.payload_json, {})
            if payload.get("operation_id") != operation_id:
                continue
            recorded_ids = tuple(int(value) for value in payload.get("analysis_ids", []))
            if recorded_ids != normalized_ids or payload.get("analysis_digest") != digest:
                raise ConcurrentVersionUpdateError(
                    f"Analysis operation {operation_id} was reused for a different analysis set"
                )
            return AnalysisVersionPublishResult(
                case_id=case.id,
                old_version=int(payload["old_version"]),
                new_version=int(payload["new_version"]),
                analysis_digest=digest,
                analysis_ids=normalized_ids,
                replayed=True,
            )

    result = advance_locked_version(db, case, "analysis_version")
    for output in outputs:
        output.analysis_version = result.new_version

    event_payload = {
        "old_version": result.old_version,
        "new_version": result.new_version,
        "analysis_digest": digest,
        "analysis_ids": list(normalized_ids),
        "material_version": case.material_version,
        "fact_version": case.fact_version,
        "issue_version": case.issue_version,
        "reason": reason,
        "source": source,
    }
    if operation_id:
        event_payload["operation_id"] = operation_id
    db.add(models.WorkflowEvent(
        case_id=case.id,
        event_type=ANALYSIS_VERSION_EVENT,
        message=f"分析版本已从 V{result.old_version} 发布至 V{result.new_version}",
        payload_json=to_json(event_payload),
    ))
    db.flush()
    return AnalysisVersionPublishResult(
        case_id=case.id,
        old_version=result.old_version,
        new_version=result.new_version,
        analysis_digest=digest,
        analysis_ids=normalized_ids,
    )
