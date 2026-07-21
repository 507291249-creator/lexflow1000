from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session, sessionmaker

from app import models
from app.services.versioning import (
    advance_material_version,
    compute_material_digest,
    publish_fact_version,
    publish_issue_version,
)
from app.services.versioning.common import case_lock_statement


@pytest.fixture()
def db(tmp_path) -> Session:
    engine = create_engine(f"sqlite:///{tmp_path / 'versioning.db'}")
    models.Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def add_case(db: Session) -> models.Case:
    case = models.Case(
        title="版本推进测试",
        claimant="甲",
        employer="乙",
        material_version=1,
        fact_version=2,
        issue_version=3,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def add_document(
    db: Session,
    case: models.Case,
    *,
    filename: str,
    checksum: str,
    processing_status: str = "ready",
) -> models.Document:
    document = models.Document(
        case_id=case.id,
        filename=filename,
        original_filename=filename,
        file_type="txt",
        mime_type="text/plain",
        checksum=checksum,
        processing_status=processing_status,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def test_material_fact_and_issue_versions_increment_once(db: Session) -> None:
    case = add_case(db)
    add_document(db, case, filename="材料.txt", checksum="a" * 64)

    material = advance_material_version(
        db,
        case.id,
        reason="材料集发布",
        source="versioning_test",
    )
    fact = publish_fact_version(db, case.id)
    issue = publish_issue_version(db, case.id)
    db.commit()
    db.refresh(case)

    assert (material.old_version, material.new_version) == (1, 2)
    assert (fact.old_version, fact.new_version) == (2, 3)
    assert (issue.old_version, issue.new_version) == (3, 4)
    assert case.material_version == 2
    assert case.fact_version == 3
    assert case.issue_version == 4
    assert case.material_digest == material.material_digest


def test_case_lock_and_stale_session_prevent_lost_updates(tmp_path) -> None:
    database_path = tmp_path / "concurrency.db"
    engine = create_engine(f"sqlite:///{database_path}")
    models.Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    setup = session_factory()
    first = session_factory()
    stale = session_factory()
    try:
        case = models.Case(
            title="并发测试",
            claimant="甲",
            employer="乙",
            material_version=0,
        )
        setup.add(case)
        setup.commit()
        case_id = case.id
        stale_case = stale.get(models.Case, case_id)
        assert stale_case.material_version == 0

        first_result = advance_material_version(
            first,
            case_id,
            reason="第一次发布",
            source="concurrency_test",
        )
        first.commit()
        second_result = advance_material_version(
            stale,
            case_id,
            reason="第二次发布",
            source="concurrency_test",
        )
        stale.commit()

        setup.expire_all()
        assert setup.get(models.Case, case_id).material_version == 2
        assert (first_result.old_version, first_result.new_version) == (0, 1)
        assert (second_result.old_version, second_result.new_version) == (1, 2)
        sql = str(case_lock_statement(case_id).compile(dialect=postgresql.dialect()))
        assert "FOR UPDATE" in sql
    finally:
        setup.close()
        first.close()
        stale.close()
        engine.dispose()


def test_material_digest_is_stable_and_tracks_structural_inputs(db: Session) -> None:
    case = add_case(db)
    first = add_document(db, case, filename="B.txt", checksum="b" * 64)
    second = add_document(db, case, filename="A.txt", checksum="a" * 64)
    db.add(models.RedactionRecord(
        case_id=case.id,
        document_id=second.id,
        source_checksum=second.checksum,
        version=2,
        status="confirmed",
        analysis_mode="redacted",
    ))
    db.commit()

    initial = compute_material_digest(db, case.id)
    assert initial == compute_material_digest(db, case.id)
    assert len(initial) == 64

    first.processing_status = "analysis_failed"
    db.commit()
    status_changed = compute_material_digest(db, case.id)
    assert status_changed != initial

    db.add(models.RedactionRecord(
        case_id=case.id,
        document_id=second.id,
        source_checksum=second.checksum,
        version=3,
        status="original_confirmed",
        analysis_mode="original",
    ))
    db.commit()
    assert compute_material_digest(db, case.id) != status_changed


def test_filename_changes_do_not_change_material_digest(db: Session) -> None:
    case = add_case(db)
    document = add_document(db, case, filename="旧文件名.txt", checksum="c" * 64)
    before = compute_material_digest(db, case.id)

    document.filename = "新文件名.txt"
    document.original_filename = "用户重命名.txt"
    db.commit()

    assert compute_material_digest(db, case.id) == before


def test_material_advance_records_workflow_event(db: Session) -> None:
    case = add_case(db)
    result = advance_material_version(
        db,
        case.id,
        reason="脱敏版本确认",
        source="redaction_confirm",
    )
    event = db.query(models.WorkflowEvent).filter_by(
        case_id=case.id,
        event_type="MATERIAL_VERSION_ADVANCED",
    ).one()
    payload = json.loads(event.payload_json)

    assert payload == {
        "old_version": result.old_version,
        "new_version": result.new_version,
        "reason": "脱敏版本确认",
        "source": "redaction_confirm",
    }
    assert "V1" in event.message and "V2" in event.message


def test_material_version_and_event_rollback_together(db: Session) -> None:
    case = add_case(db)
    advance_material_version(
        db,
        case.id,
        reason="回滚测试",
        source="versioning_test",
    )

    db.rollback()
    db.refresh(case)

    assert case.material_version == 1
    assert case.material_digest is None
    assert db.query(models.WorkflowEvent).filter_by(case_id=case.id).count() == 0


def test_material_operation_id_is_idempotent(db: Session) -> None:
    case = add_case(db)
    first = advance_material_version(
        db,
        case.id,
        reason="首次请求",
        source="upload",
        operation_id="upload-request-001",
    )
    db.commit()

    repeated = advance_material_version(
        db,
        case.id,
        reason="客户端重试",
        source="upload",
        operation_id="upload-request-001",
    )
    db.commit()
    db.refresh(case)

    assert repeated == first
    assert case.material_version == 2
    assert db.query(models.WorkflowEvent).filter_by(
        case_id=case.id,
        event_type="MATERIAL_VERSION_ADVANCED",
    ).count() == 1
