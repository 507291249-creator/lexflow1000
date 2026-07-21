from __future__ import annotations

import hashlib
import json
from typing import Optional

from sqlalchemy.orm import Session

from ... import models
from ...utils import from_json, to_json
from .common import (
    ConcurrentVersionUpdateError,
    VersionAdvanceResult,
    advance_locked_version,
    lock_case,
)


MATERIAL_VERSION_EVENT = "MATERIAL_VERSION_ADVANCED"


def material_digest_payload(db: Session, case_id: int) -> list[dict[str, object]]:
    documents = db.query(models.Document).filter(
        models.Document.case_id == case_id
    ).order_by(models.Document.id).all()
    document_ids = [document.id for document in documents]
    latest_redactions: dict[int, models.RedactionRecord] = {}
    if document_ids:
        redactions = db.query(models.RedactionRecord).filter(
            models.RedactionRecord.case_id == case_id,
            models.RedactionRecord.document_id.in_(document_ids),
        ).order_by(
            models.RedactionRecord.document_id,
            models.RedactionRecord.version.desc(),
            models.RedactionRecord.id.desc(),
        ).all()
        for redaction in redactions:
            latest_redactions.setdefault(redaction.document_id, redaction)

    return [
        {
            "document_id": document.id,
            "checksum": document.checksum or "",
            "processing_status": document.processing_status or "",
            "redaction_version": latest_redactions[document.id].version
            if document.id in latest_redactions else 0,
            "analysis_mode": latest_redactions[document.id].analysis_mode
            if document.id in latest_redactions else "",
        }
        for document in documents
    ]


def compute_material_digest(db: Session, case_id: int) -> str:
    payload = material_digest_payload(db, case_id)
    canonical = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def advance_material_version(
    db: Session,
    case_id: int,
    *,
    reason: str,
    source: str,
    operation_id: Optional[str] = None,
) -> VersionAdvanceResult:
    """Advance material lineage inside the caller's active transaction."""
    case = lock_case(db, case_id)
    if operation_id:
        events = db.query(models.WorkflowEvent).filter(
            models.WorkflowEvent.case_id == case.id,
            models.WorkflowEvent.event_type == MATERIAL_VERSION_EVENT,
        ).order_by(models.WorkflowEvent.id.desc()).all()
        for event in events:
            payload = from_json(event.payload_json, {})
            if payload.get("operation_id") == operation_id:
                current_digest = compute_material_digest(db, case.id)
                recorded_digest = payload.get("material_digest")
                if recorded_digest != current_digest:
                    raise ConcurrentVersionUpdateError(
                        f"Material operation {operation_id} was reused for a different material set"
                    )
                return VersionAdvanceResult(
                    case_id=case.id,
                    old_version=int(payload["old_version"]),
                    new_version=int(payload["new_version"]),
                    material_digest=recorded_digest or case.material_digest,
                )
    digest = compute_material_digest(db, case.id)
    result = advance_locked_version(
        db,
        case,
        "material_version",
        extra_values={"material_digest": digest},
    )
    payload = {
        "old_version": result.old_version,
        "new_version": result.new_version,
        "reason": reason,
        "source": source,
    }
    if operation_id:
        payload.update({
            "operation_id": operation_id,
            "material_digest": digest,
        })
    event = models.WorkflowEvent(
        case_id=case.id,
        event_type=MATERIAL_VERSION_EVENT,
        message=f"材料版本已从 V{result.old_version} 推进至 V{result.new_version}",
        payload_json=to_json(payload),
    )
    db.add(event)
    db.flush()
    return result
