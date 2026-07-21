from sqlalchemy.orm import Session

from .common import VersionAdvanceResult, advance_locked_version, lock_case


def publish_fact_version(db: Session, case_id: int) -> VersionAdvanceResult:
    """Publish one complete fact set; individual fact reviews must not call this."""
    case = lock_case(db, case_id)
    result = advance_locked_version(db, case, "fact_version")
    db.flush()
    return result
