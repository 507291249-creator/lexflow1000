from sqlalchemy.orm import Session
from typing import Optional

from .. import models
from ..utils import join_tags


def create_trace(
    db: Session,
    case_id: int,
    ai_output_id: Optional[int],
    ai_suggestion: str,
    human_revision: str,
    revision_reason: str,
    tags: list[str],
) -> models.DecisionTrace:
    trace = models.DecisionTrace(
        case_id=case_id,
        ai_output_id=ai_output_id,
        ai_suggestion=ai_suggestion,
        human_revision=human_revision,
        revision_reason=revision_reason,
        tags=join_tags(tags),
    )
    db.add(trace)
    db.commit()
    db.refresh(trace)
    return trace
