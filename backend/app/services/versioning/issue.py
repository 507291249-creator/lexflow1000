from sqlalchemy.orm import Session

from .common import VersionAdvanceResult, advance_locked_version, lock_case


def publish_issue_version(db: Session, case_id: int) -> VersionAdvanceResult:
    """Publish one complete issue set; individual issue reviews must not call this."""
    case = lock_case(db, case_id)
    result = advance_locked_version(db, case, "issue_version")
    db.flush()
    return result
