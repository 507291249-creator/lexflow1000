from __future__ import annotations

import io
import json
import os
import tempfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import Request, urlopen

from docx import Document as DocxDocument
from fastapi import UploadFile
from pypdf import PdfWriter
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.datastructures import Headers

from app.database import Base
from app.main import delete_document, persist_prepared_document
from app.models import Case, Document
from app.services.document_files import ALLOWED_FILE_TYPES, prepare_upload
from app.services.storage import get_storage_service


REQUIRED_ENV = (
    "STORAGE_PROVIDER",
    "S3_ENDPOINT_URL",
    "S3_ACCESS_KEY_ID",
    "S3_SECRET_ACCESS_KEY",
    "S3_BUCKET_NAME",
)


def require_non_production_configuration() -> None:
    missing = [name for name in REQUIRED_ENV if not os.getenv(name, "").strip()]
    if missing:
        raise RuntimeError(f"缺少对象存储验证配置：{', '.join(missing)}")
    if os.getenv("STORAGE_VALIDATION_NON_PRODUCTION", "").lower() != "true":
        raise RuntimeError("必须显式设置 STORAGE_VALIDATION_NON_PRODUCTION=true")
    bucket = os.environ["S3_BUCKET_NAME"].lower()
    if not any(marker in bucket for marker in ("test", "staging", "validation", "sandbox")):
        raise RuntimeError("验证桶名称必须包含 test、staging、validation 或 sandbox")
    if os.environ["STORAGE_PROVIDER"].lower() not in {"r2", "s3"}:
        raise RuntimeError("真实链路验证仅支持 STORAGE_PROVIDER=r2 或 s3")


def make_samples() -> list[tuple[str, str, bytes]]:
    text = "LexFlow 对象存储验证材料。"

    docx_buffer = io.BytesIO()
    docx = DocxDocument()
    docx.add_paragraph(text)
    docx.save(docx_buffer)

    pdf_buffer = io.BytesIO()
    pdf = PdfWriter()
    pdf.add_blank_page(width=612, height=792)
    pdf.write(pdf_buffer)

    return [
        ("storage-validation.txt", "text/plain", text.encode("utf-8")),
        (
            "storage-validation.docx",
            ALLOWED_FILE_TYPES[".docx"],
            docx_buffer.getvalue(),
        ),
        ("storage-validation.pdf", "application/pdf", pdf_buffer.getvalue()),
    ]


def prepared_upload(filename: str, mime_type: str, content: bytes):
    upload = UploadFile(
        filename=filename,
        file=io.BytesIO(content),
        headers=Headers({"content-type": mime_type}),
    )
    return prepare_upload(upload)


def verify_presigned_download(url: str, expected: bytes) -> None:
    query = {key.lower(): value for key, value in parse_qs(urlparse(url).query).items()}
    if query.get("x-amz-expires") != ["300"]:
        raise AssertionError("签名地址有效期不是 300 秒")
    with urlopen(Request(url, method="GET"), timeout=30) as response:
        if response.read() != expected:
            raise AssertionError("签名下载内容与上传内容不一致")


def verify_anonymous_access_denied(endpoint: str, bucket: str, key: str) -> int:
    anonymous_url = f"{endpoint.rstrip('/')}/{quote(bucket)}/{quote(key, safe='/')}"
    try:
        with urlopen(Request(anonymous_url, method="GET"), timeout=20) as response:
            status = response.status
    except HTTPError as exc:
        status = exc.code
    if status not in {401, 403, 404}:
        raise AssertionError(f"匿名访问未被拒绝，HTTP 状态：{status}")
    return status


def run() -> dict:
    require_non_production_configuration()
    storage = get_storage_service()
    endpoint = os.environ["S3_ENDPOINT_URL"]
    bucket = os.environ["S3_BUCKET_NAME"]
    samples = make_samples()
    results = []

    with tempfile.TemporaryDirectory(prefix="lexflow-storage-validation-") as directory:
        engine = create_engine(f"sqlite:///{Path(directory) / 'validation.db'}")
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()
        case = Case(title="Sprint 1B.5 存储验证", claimant="测试方", employer="测试方")
        session.add(case)
        session.commit()
        session.refresh(case)
        created_keys: list[str] = []
        try:
            for filename, mime_type, content in samples:
                document = persist_prepared_document(
                    session,
                    case.id,
                    prepared_upload(filename, mime_type, content),
                    storage,
                )
                if not document.storage_key or not storage.exists(document.storage_key):
                    raise AssertionError(f"对象未持久保存：{filename}")
                created_keys.append(document.storage_key)
                if document.storage_provider != os.environ["STORAGE_PROVIDER"].lower():
                    raise AssertionError(f"storage_provider 不正确：{filename}")
                if document.file_size != len(content):
                    raise AssertionError(f"file_size 不正确：{filename}")
                with storage.open_stream(document.storage_key) as stream:
                    stored = stream.read()
                if document.checksum != __import__("hashlib").sha256(content).hexdigest():
                    raise AssertionError(f"checksum 不正确：{filename}")
                if stored != content:
                    raise AssertionError(f"对象内容不正确：{filename}")

                signed_url = storage.create_presigned_download_url(document.storage_key, expires_in=300)
                if not signed_url:
                    raise AssertionError(f"未生成签名地址：{filename}")
                verify_presigned_download(signed_url, content)
                anonymous_status = verify_anonymous_access_denied(
                    endpoint,
                    bucket,
                    document.storage_key,
                )

                document_id = document.id
                object_key = document.storage_key
                delete_document(case.id, document_id, session)
                if session.query(Document).filter(Document.id == document_id).first():
                    raise AssertionError(f"数据库记录未删除：{filename}")
                if storage.exists(object_key):
                    raise AssertionError(f"对象未删除：{filename}")
                created_keys.remove(object_key)
                results.append(
                    {
                        "filename": filename,
                        "file_size": len(content),
                        "checksum": __import__("hashlib").sha256(content).hexdigest(),
                        "storage_provider": os.environ["STORAGE_PROVIDER"].lower(),
                        "storage_key": object_key,
                        "presigned_expires_in": 300,
                        "anonymous_http_status": anonymous_status,
                        "deleted": True,
                    }
                )
        finally:
            for key in created_keys:
                try:
                    storage.delete(key)
                except Exception:
                    pass
            session.close()
            engine.dispose()

    return {"ok": True, "bucket": bucket, "documents": results}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
