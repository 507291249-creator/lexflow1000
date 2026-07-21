from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.datastructures import Headers

from app.database import Base
from app import main as main_module
from app.main import delete_document, document_storage, persist_prepared_document, serialize_document
from app.models import Case, Document
from app.services.document_files import PreparedUpload, calculate_checksum, prepare_upload
from app.services.storage import (
    LocalStorageService,
    S3CompatibleStorageService,
    StorageConfigurationError,
    StorageError,
    build_object_key,
    get_storage_service,
)


def make_prepared(content: bytes = b"example legal text", filename: str = "case.txt") -> PreparedUpload:
    stream = io.BytesIO(content)
    return PreparedUpload(
        original_filename=filename,
        safe_filename=filename,
        file_type="txt",
        mime_type="text/plain",
        file_size=len(content),
        checksum=calculate_checksum(stream),
        stream=stream,
    )


@pytest.fixture()
def db_session(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'storage.db'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    case = Case(title="存储测试", claimant="甲", employer="乙")
    session.add(case)
    session.commit()
    session.refresh(case)
    try:
        yield session, case
    finally:
        session.close()
        engine.dispose()


def test_local_storage_put_read_exists_and_delete(tmp_path: Path):
    storage = LocalStorageService(tmp_path / "objects")
    key = build_object_key(1, 2, "a" * 64, "证据.txt")
    storage.put(key, io.BytesIO(b"hello"), "text/plain")
    assert storage.exists(key)
    with storage.open_stream(key) as stream:
        assert stream.read() == b"hello"
    downloaded = storage.download_to_temp(key, ".txt")
    assert downloaded.read_bytes() == b"hello"
    downloaded.unlink()
    storage.delete(key)
    assert not storage.exists(key)


def test_local_storage_rejects_path_traversal(tmp_path: Path):
    storage = LocalStorageService(tmp_path / "objects")
    with pytest.raises(StorageError):
        storage.put("../outside.txt", io.BytesIO(b"bad"), "text/plain")
    assert not (tmp_path / "outside.txt").exists()


def test_checksum_is_stable_and_rewinds_stream():
    stream = io.BytesIO(b"same bytes")
    first = calculate_checksum(stream)
    second = calculate_checksum(stream)
    assert first == second
    assert len(first) == 64
    assert stream.tell() == 0


def test_same_filename_uses_distinct_document_keys():
    checksum = "b" * 64
    first = build_object_key(7, 10, checksum, "合同.txt")
    second = build_object_key(7, 11, checksum, "合同.txt")
    assert first != second
    assert first.startswith("cases/7/documents/10/")


def test_duplicate_file_in_same_case_is_rejected(db_session, tmp_path: Path):
    db, case = db_session
    storage = LocalStorageService(tmp_path / "objects")
    persist_prepared_document(db, case.id, make_prepared(), storage)
    with pytest.raises(HTTPException) as exc:
        persist_prepared_document(db, case.id, make_prepared(), storage)
    assert exc.value.status_code == 409
    assert db.query(Document).filter(Document.case_id == case.id).count() == 1


def test_object_upload_failure_keeps_error_document(db_session, tmp_path: Path):
    class FailingStorage(LocalStorageService):
        provider_name = "local"

        def put(self, key, source, content_type):
            raise StorageError("simulated failure")

    db, case = db_session
    storage = FailingStorage(tmp_path / "objects")
    with pytest.raises(HTTPException) as exc:
        persist_prepared_document(db, case.id, make_prepared(), storage)
    assert exc.value.status_code == 502
    document = db.query(Document).filter(Document.case_id == case.id).one()
    assert document.processing_status == "upload_failed"
    assert document.storage_key is None


def test_partial_upload_failure_compensates_object(db_session, tmp_path: Path):
    class PartiallyFailingStorage(LocalStorageService):
        provider_name = "local"

        def put(self, key, source, content_type):
            super().put(key, source, content_type)
            raise StorageError("provider acknowledgement failed")

    db, case = db_session
    root = tmp_path / "objects"
    storage = PartiallyFailingStorage(root)
    with pytest.raises(HTTPException) as exc:
        persist_prepared_document(db, case.id, make_prepared(), storage)
    assert exc.value.status_code == 502
    assert not any(path.is_file() for path in root.rglob("*"))


def test_database_state_failure_compensates_uploaded_object(db_session, tmp_path: Path, monkeypatch):
    db, case = db_session
    root = tmp_path / "objects"
    storage = LocalStorageService(root)
    original_commit = db.commit
    commit_failed = False

    def fail_final_commit_once():
        nonlocal commit_failed
        if not commit_failed:
            commit_failed = True
            raise RuntimeError("simulated database failure")
        return original_commit()

    monkeypatch.setattr(db, "commit", fail_final_commit_once)
    with pytest.raises(HTTPException) as exc:
        persist_prepared_document(db, case.id, make_prepared(), storage)
    assert exc.value.status_code == 500
    assert not any(path.is_file() for path in root.rglob("*"))
    assert db.query(Document).filter(Document.case_id == case.id).count() == 0
    db.refresh(case)
    assert case.material_version == 0
    assert db.query(main_module.models.WorkflowEvent).filter_by(case_id=case.id).count() == 0


def test_parse_failure_keeps_original_object(db_session, tmp_path: Path, monkeypatch):
    db, case = db_session
    storage = LocalStorageService(tmp_path / "objects")

    def fail_parse(_path):
        raise ValueError("simulated parse failure")

    monkeypatch.setattr(main_module, "parse_document", fail_parse)
    document = persist_prepared_document(db, case.id, make_prepared(), storage)
    assert document.processing_status == "parse_failed"
    assert document.storage_key
    assert storage.exists(document.storage_key)


def test_delete_failure_keeps_database_record(db_session, tmp_path: Path, monkeypatch):
    class FailingDeleteStorage(LocalStorageService):
        provider_name = "local"

        def delete(self, key):
            raise StorageError("simulated delete failure")

    db, case = db_session
    root = tmp_path / "objects"
    storage = LocalStorageService(root)
    document = persist_prepared_document(db, case.id, make_prepared(), storage)
    failing_storage = FailingDeleteStorage(root)
    monkeypatch.setattr(main_module, "get_storage_service", lambda provider=None: failing_storage)

    with pytest.raises(HTTPException) as exc:
        delete_document(case.id, document.id, db)
    assert exc.value.status_code == 503
    assert db.query(Document).filter(Document.id == document.id).one_or_none() is not None
    assert storage.exists(document.storage_key)


def test_legacy_local_document_remains_readable_without_fake_download(db_session):
    db, case = db_session
    document = Document(
        case_id=case.id,
        filename="old.txt",
        original_filename="old.txt",
        file_type="txt",
        mime_type="text/plain",
        storage_provider="legacy_local",
        raw_text="旧材料解析文本",
        processing_status="ready",
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    assert serialize_document(document)["raw_text"] == "旧材料解析文本"
    with pytest.raises(HTTPException) as exc:
        document_storage(document)
    assert exc.value.status_code == 410


def test_s3_presigned_url_uses_private_get_object():
    class FakeS3Client:
        def generate_presigned_url(self, operation, Params, ExpiresIn):
            assert operation == "get_object"
            assert Params == {"Bucket": "private-bucket", "Key": "cases/1/file.txt"}
            assert ExpiresIn == 300
            return "https://storage.example/signed"

    storage = S3CompatibleStorageService(bucket_name="private-bucket", client=FakeS3Client())
    assert storage.create_presigned_download_url("cases/1/file.txt") == "https://storage.example/signed"


def test_s3_operations_use_configured_private_bucket():
    class FakeBody(io.BytesIO):
        pass

    class FakeS3Client:
        def __init__(self):
            self.objects = {}

        def upload_fileobj(self, source, bucket, key, ExtraArgs):
            assert bucket == "private-bucket"
            assert ExtraArgs == {"ContentType": "text/plain"}
            self.objects[key] = source.read()

        def head_object(self, Bucket, Key):
            assert Bucket == "private-bucket"
            if Key not in self.objects:
                error = RuntimeError("not found")
                error.response = {
                    "ResponseMetadata": {"HTTPStatusCode": 404},
                    "Error": {"Code": "NoSuchKey"},
                }
                raise error
            return {}

        def get_object(self, Bucket, Key):
            assert Bucket == "private-bucket"
            return {"Body": FakeBody(self.objects[Key])}

        def delete_object(self, Bucket, Key):
            assert Bucket == "private-bucket"
            self.objects.pop(Key, None)

    client = FakeS3Client()
    storage = S3CompatibleStorageService(bucket_name="private-bucket", client=client)
    key = "cases/1/documents/2/file.txt"
    storage.put(key, io.BytesIO(b"private"), "text/plain")
    assert storage.exists(key)
    assert storage.open_stream(key).read() == b"private"
    storage.delete(key)
    assert not storage.exists(key)


def test_render_requires_explicit_storage_provider(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.delenv("STORAGE_PROVIDER", raising=False)
    with pytest.raises(StorageConfigurationError):
        get_storage_service()


def test_illegal_file_type_and_mime_mismatch_are_rejected():
    illegal = UploadFile(
        filename="payload.exe",
        file=io.BytesIO(b"MZ"),
        headers=Headers({"content-type": "application/octet-stream"}),
    )
    with pytest.raises(HTTPException) as exc:
        prepare_upload(illegal)
    assert exc.value.status_code == 400

    mismatch = UploadFile(
        filename="contract.pdf",
        file=io.BytesIO(b"%PDF-1.7"),
        headers=Headers({"content-type": "text/plain"}),
    )
    with pytest.raises(HTTPException) as exc:
        prepare_upload(mismatch)
    assert exc.value.status_code == 400


def test_file_size_limit_is_enforced():
    upload = UploadFile(
        filename="large.txt",
        file=io.BytesIO(b"12345"),
        headers=Headers({"content-type": "text/plain"}),
    )
    with pytest.raises(HTTPException) as exc:
        prepare_upload(upload, size_limit=4)
    assert exc.value.status_code == 413
