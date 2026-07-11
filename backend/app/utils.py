import json
from typing import Any, Optional, Union

from sqlalchemy.orm import Session

from . import models


def to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def from_json(value: Optional[str], default: Any = None) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def split_tags(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def join_tags(tags: Optional[Union[list[str], str]]) -> str:
    if isinstance(tags, str):
        return tags
    return ",".join(tags or [])


def log_event(db: Session, case_id: int, event_type: str, message: str, payload: Any = None) -> models.WorkflowEvent:
    event = models.WorkflowEvent(
        case_id=case_id,
        event_type=event_type,
        message=message,
        payload_json=to_json(payload or {}),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
