from __future__ import annotations

import io
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app import main as main_module, models
from app.main import (
    delete_document,
    download_document,
    get_document_download_url,
    persist_prepared_document,
)
from app.services.document_files import PreparedUpload, calculate_checksum
from app.services.storage import LocalStorageService


@pytest.fixture()
def db(tmp_path) -> Session:
    engine = create_engine(f"sqlite:///{tmp_path / 'material-integration.db'}")
    models.Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    case = models.Case(title="材料版本接入测试", claimant="甲", employer="乙")
    session.add(case)
    session.commit()
    session.refresh(case)
    session.test_case = case
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def prepared_upload(content: bytes = b"material input") -> PreparedUpload:
    stream = io.BytesIO(content)
    return PreparedUpload(
        original_filename="材料.txt",
        safe_filename="材料.txt",
        file_type="txt",
        mime_type="text/plain",
        file_size=len(content),
        checksum=calculate_checksum(stream),
        stream=stream,
    )


def material_events(db: Session, case_id: int) -> list[models.WorkflowEvent]:
    return db.query(models.WorkflowEvent).filter_by(
        case_id=case_id,
        event_type="MATERIAL_VERSION_ADVANCED",
    ).order_by(models.WorkflowEvent.id).all()


def test_document_create_advances_material_version_once(db: Session, tmp_path) -> None:
    case = db.test_case
    storage = LocalStorageService(tmp_path / "objects")

    document = persist_prepared_document(db, case.id, prepared_upload(), storage)
    db.refresh(case)

    assert document.processing_status == "ready"
    assert document.raw_text == "material input"
    assert case.material_version == 1
    assert case.material_digest
    events = material_events(db, case.id)
    assert len(events) == 1
    assert json.loads(events[0].payload_json)["source"] == "document_upload"


def test_document_delete_advances_material_version(
    db: Session,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = db.test_case
    storage = LocalStorageService(tmp_path / "objects")
    document = persist_prepared_document(db, case.id, prepared_upload(), storage)
    monkeypatch.setattr(main_module, "get_storage_service", lambda provider=None: storage)

    result = delete_document(case.id, document.id, db)
    db.refresh(case)

    assert result == {"ok": True}
    assert case.material_version == 2
    assert db.query(models.Document).filter_by(id=document.id).one_or_none() is None
    assert len(material_events(db, case.id)) == 2


def test_filename_change_does_not_advance_material_version(db: Session, tmp_path) -> None:
    case = db.test_case
    storage = LocalStorageService(tmp_path / "objects")
    document = persist_prepared_document(db, case.id, prepared_upload(), storage)
    original_digest = case.material_digest

    document.filename = "展示名称.txt"
    document.original_filename = "用户展示名称.txt"
    db.commit()
    db.refresh(case)

    assert case.material_version == 1
    assert case.material_digest == original_digest
    assert len(material_events(db, case.id)) == 1


def test_download_and_signed_url_do_not_advance_material_version(
    db: Session,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = db.test_case
    storage = LocalStorageService(tmp_path / "objects")
    document = persist_prepared_document(db, case.id, prepared_upload(), storage)
    monkeypatch.setattr(main_module, "get_storage_service", lambda provider=None: storage)

    class RequestStub:
        @staticmethod
        def url_for(_name, **kwargs):
            return f"http://test/documents/{kwargs['document_id']}/download"

    signed = get_document_download_url(document.id, RequestStub(), db)
    response = download_document(document.id, db)
    db.refresh(case)

    assert signed["url"].endswith(f"/documents/{document.id}/download")
    assert response.status_code == 200
    assert case.material_version == 1
    assert len(material_events(db, case.id)) == 1


def test_delete_transaction_failure_restores_document_and_object(
    db: Session,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = db.test_case
    storage = LocalStorageService(tmp_path / "objects")
    document = persist_prepared_document(db, case.id, prepared_upload(), storage)
    storage_key = document.storage_key
    monkeypatch.setattr(main_module, "get_storage_service", lambda provider=None: storage)

    def fail_version(*_args, **_kwargs):
        raise RuntimeError("simulated versioning failure")

    monkeypatch.setattr(main_module, "advance_material_version", fail_version)

    with pytest.raises(RuntimeError, match="simulated versioning failure"):
        delete_document(case.id, document.id, db)
    db.refresh(case)

    assert db.query(models.Document).filter_by(id=document.id).one_or_none() is not None
    assert storage.exists(storage_key)
    assert case.material_version == 1
    assert len(material_events(db, case.id)) == 1
