from typing import Any, Iterable, Optional

from ...schemas import BlockerSchema, WorkflowStepCode
from .constants import BLOCKER_ACTION_LABELS, BlockerCode


def make_blocker(
    code: BlockerCode,
    step: WorkflowStepCode,
    message: str,
    *,
    entity_type: Optional[str] = None,
    entity_ids: Iterable[int] = (),
    resolution: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
) -> BlockerSchema:
    return BlockerSchema(
        code=code.value,
        step=step,
        severity="blocking",
        message=message,
        entity_type=entity_type,
        entity_ids=list(entity_ids),
        resolution=resolution or BLOCKER_ACTION_LABELS[code],
        details=details or {},
    )
