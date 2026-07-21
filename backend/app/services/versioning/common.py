from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ... import models


class VersioningError(RuntimeError):
    pass


class CaseNotFoundError(VersioningError):
    pass


class ConcurrentVersionUpdateError(VersioningError):
    pass


@dataclass(frozen=True)
class VersionAdvanceResult:
    case_id: int
    old_version: int
    new_version: int
    material_digest: Optional[str] = None


def case_lock_statement(case_id: int):
    return select(models.Case).where(
        models.Case.id == case_id
    ).with_for_update().execution_options(populate_existing=True)


def lock_case(db: Session, case_id: int) -> models.Case:
    case = db.execute(case_lock_statement(case_id)).scalar_one_or_none()
    if not case:
        raise CaseNotFoundError(f"Case {case_id} does not exist")
    return case


def advance_locked_version(
    db: Session,
    case: models.Case,
    field: str,
    *,
    extra_values: Optional[dict[str, Any]] = None,
) -> VersionAdvanceResult:
    column = getattr(models.Case, field)
    old_version = int(getattr(case, field) or 0)
    new_version = old_version + 1
    values = {field: new_version, **(extra_values or {})}
    result = db.execute(
        update(models.Case).where(
            models.Case.id == case.id,
            column == old_version,
        ).values(**values).execution_options(synchronize_session="fetch")
    )
    if result.rowcount != 1:
        raise ConcurrentVersionUpdateError(
            f"Case {case.id} {field} changed while the version was being advanced"
        )
    return VersionAdvanceResult(
        case_id=case.id,
        old_version=old_version,
        new_version=new_version,
        material_digest=values.get("material_digest"),
    )
