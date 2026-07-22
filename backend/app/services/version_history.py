from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from .. import models, schemas
from ..utils import from_json, split_tags
from .workflow.stale import collect_stale_outputs


VERSION_EVENTS = {
    "MATERIAL_VERSION_ADVANCED": ("material", "material_version"),
    "FACT_VERSION_PUBLISHED": ("fact", "fact_version"),
    "ISSUE_VERSION_PUBLISHED": ("issue", "issue_version"),
    "ANALYSIS_VERSION_PUBLISHED": ("analysis", "analysis_version"),
    "REPORT_VERSION_PUBLISHED": ("report", "report_version"),
}


@dataclass(frozen=True)
class _SortableEntry:
    created_at: datetime
    source_order: int
    numeric_id: int
    value: Any


def _int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _versions(payload: dict[str, Any], *, prefix: str = "") -> dict[str, int] | None:
    result: dict[str, int] = {}
    for key in (
        "material_version",
        "fact_version",
        "issue_version",
        "analysis_version",
        "report_version",
    ):
        value = _int(payload.get(f"{prefix}{key}"))
        if value is not None:
            result[key] = value
    return result or None


def _event_versions(payload: dict[str, Any], axis: str) -> tuple[dict[str, int], dict[str, int]]:
    before = _versions(payload) or {}
    after = dict(before)
    old_version = _int(payload.get("old_version"))
    new_version = _int(payload.get("new_version"))
    if old_version is not None:
        before[axis] = old_version
    if new_version is not None:
        after[axis] = new_version
    return before, after


def _event_object_id(payload: dict[str, Any], object_type: str) -> int | None:
    singular = {
        "material": "document_id",
        "fact": "fact_id",
        "issue": "issue_id",
        "analysis": "analysis_id",
        "report": "report_id",
    }[object_type]
    return _int(payload.get(singular))


def _event_digest(payload: dict[str, Any]) -> str | None:
    for key in ("report_digest", "analysis_digest", "material_digest"):
        value = payload.get(key)
        if value:
            return str(value)
    return None


def get_version_history(
    db: Session,
    case: models.Case,
    *,
    page: int,
    page_size: int,
) -> schemas.VersionHistoryPage:
    current = schemas.WorkflowVersionsSchema(
        material_version=case.material_version,
        fact_version=case.fact_version,
        issue_version=case.issue_version,
        analysis_version=case.analysis_version,
        report_version=case.report_version,
    )
    stale_by_key = {
        (item.entity_type, item.entity_id): item
        for item in collect_stale_outputs(db, case)
    }
    entries: list[_SortableEntry] = []
    outputs = db.query(models.AIOutput).filter(
        models.AIOutput.case_id == case.id
    ).all()
    latest_output_ids: dict[tuple[int | None, str], int] = {}
    for output in sorted(outputs, key=lambda item: (item.version or 0, item.id or 0)):
        latest_output_ids[(output.work_unit_id, output.output_type)] = output.id
    for output in outputs:
        object_type = {
            "fact_extraction": "fact",
            "issue_identification": "issue",
            "legal_analysis": "analysis",
            "legal_report": "report",
        }.get(output.output_type, output.output_type)
        stale = stale_by_key.get((object_type, output.id))
        input_versions = {
            "material_version": output.material_version,
            "fact_version": output.fact_version,
            "issue_version": output.issue_version,
            "analysis_version": output.analysis_version,
            "report_version": output.report_version,
        }
        published_version = {
            "analysis": output.analysis_version,
            "report": output.report_version,
        }.get(object_type)
        compared_axes = {
            "fact": ("material_version",),
            "issue": ("material_version", "fact_version"),
            "analysis": ("material_version", "fact_version", "issue_version"),
            "report": (
                "material_version",
                "fact_version",
                "issue_version",
                "analysis_version",
                "report_version",
            ),
        }.get(object_type, ("material_version", "fact_version", "issue_version"))
        changed_axes = [
            key for key in compared_axes
            if input_versions[key] != getattr(case, key)
        ]
        latest_generation = latest_output_ids[(output.work_unit_id, output.output_type)] == output.id
        stale_reason = stale.stale_reason if stale else None
        if not latest_generation:
            stale_reason = "generation_superseded"
        elif changed_axes and not stale_reason:
            stale_reason = (
                f"{changed_axes[0]}_changed"
                if len(changed_axes) == 1
                else "input_versions_changed"
            )
        is_current = latest_generation and not changed_axes and stale is None
        value = schemas.VersionHistoryEntry(
            event_id=f"generation:{output.id}",
            entry_type="generation",
            event_type=f"{output.output_type.upper()}_GENERATED",
            object_type=object_type,
            object_id=output.id,
            ai_output_id=output.id,
            work_unit_id=output.work_unit_id,
            generation_version=output.version,
            published_version=published_version if published_version and published_version > 0 else None,
            input_versions=input_versions,
            is_current=is_current,
            is_stale=not is_current,
            stale_reason=stale_reason,
            created_at=output.created_at,
        )
        entries.append(_SortableEntry(output.created_at, 0, output.id, value))

    events = db.query(models.WorkflowEvent).filter(
        models.WorkflowEvent.case_id == case.id,
        models.WorkflowEvent.event_type.in_(VERSION_EVENTS),
    ).all()
    for event in events:
        object_type, axis = VERSION_EVENTS[event.event_type]
        payload = from_json(event.payload_json, {})
        before, after = _event_versions(payload, axis)
        published_version = _int(payload.get("new_version"))
        object_id = _event_object_id(payload, object_type)
        is_current = published_version == getattr(case, axis)
        value = schemas.VersionHistoryEntry(
            event_id=f"workflow_event:{event.id}",
            entry_type="publication",
            event_type=event.event_type,
            object_type=object_type,
            object_id=object_id,
            ai_output_id=_int(payload.get("report_id")) if object_type == "report" else None,
            generation_version=None,
            published_version=published_version if published_version and published_version > 0 else None,
            before_versions=before,
            after_versions=after,
            input_versions=_versions(payload),
            digest=_event_digest(payload),
            reason=str(payload["reason"]) if payload.get("reason") is not None else None,
            is_current=is_current,
            is_stale=not is_current,
            stale_reason=None if is_current else f"{axis}_superseded",
            created_at=event.created_at,
        )
        entries.append(_SortableEntry(event.created_at, 1, event.id, value))

    entries.sort(
        key=lambda item: (item.created_at, item.source_order, item.numeric_id),
        reverse=True,
    )
    start = (page - 1) * page_size
    return schemas.VersionHistoryPage(
        current_versions=current,
        page=page,
        page_size=page_size,
        total=len(entries),
        items=[item.value for item in entries[start:start + page_size]],
    )


def get_reasoning_trace(
    db: Session,
    case: models.Case,
    *,
    page: int,
    page_size: int,
) -> schemas.ReasoningTracePage:
    entries: list[_SortableEntry] = []
    traces = db.query(models.DecisionTrace).filter(
        models.DecisionTrace.case_id == case.id
    ).all()
    for trace in traces:
        value = schemas.ReasoningTraceEntry(
            event_id=f"decision_trace:{trace.id}",
            event_source="decision_trace",
            event_type="HUMAN_DECISION",
            action=trace.action,
            object_type=trace.object_type,
            object_id=trace.object_id,
            ai_output_id=trace.ai_output_id,
            work_unit_id=trace.work_unit_id,
            ai_suggestion=trace.ai_suggestion,
            human_revision=trace.human_revision,
            revision_reason=trace.revision_reason,
            tags=split_tags(trace.tags),
            created_at=trace.created_at,
        )
        entries.append(_SortableEntry(trace.created_at, 1, trace.id, value))

    events = db.query(models.WorkflowEvent).filter(
        models.WorkflowEvent.case_id == case.id,
        models.WorkflowEvent.event_type.in_(VERSION_EVENTS),
    ).all()
    for event in events:
        object_type, axis = VERSION_EVENTS[event.event_type]
        payload = from_json(event.payload_json, {})
        before, after = _event_versions(payload, axis)
        value = schemas.ReasoningTraceEntry(
            event_id=f"workflow_event:{event.id}",
            event_source="workflow_event",
            event_type=event.event_type,
            action="publish" if event.event_type != "MATERIAL_VERSION_ADVANCED" else "advance",
            object_type=object_type,
            object_id=_event_object_id(payload, object_type),
            ai_output_id=_int(payload.get("report_id")) if object_type == "report" else None,
            work_unit_id=_int(payload.get("work_unit_id")),
            revision_reason=str(payload["reason"]) if payload.get("reason") is not None else None,
            tags=None,
            before_versions=before,
            after_versions=after,
            input_versions=_versions(payload),
            created_at=event.created_at,
        )
        entries.append(_SortableEntry(event.created_at, 0, event.id, value))

    entries.sort(
        key=lambda item: (item.created_at, item.source_order, item.numeric_id),
        reverse=True,
    )
    start = (page - 1) * page_size
    return schemas.ReasoningTracePage(
        page=page,
        page_size=page_size,
        total=len(entries),
        items=[item.value for item in entries[start:start + page_size]],
    )
