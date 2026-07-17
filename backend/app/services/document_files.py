from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from fastapi import HTTPException, UploadFile

from .storage import safe_filename


DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
ALLOWED_FILE_TYPES = {
    ".pdf": "application/pdf",
    ".docx": DOCX_MIME,
    ".txt": "text/plain",
}
DEFAULT_MAX_UPLOAD_SIZE = 20 * 1024 * 1024


@dataclass
class PreparedUpload:
    original_filename: str
    safe_filename: str
    file_type: str
    mime_type: str
    file_size: int
    checksum: str
    stream: BinaryIO

    def close(self) -> None:
        self.stream.close()


def max_upload_size() -> int:
    raw = os.getenv("MAX_UPLOAD_SIZE_BYTES", str(DEFAULT_MAX_UPLOAD_SIZE))
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError("MAX_UPLOAD_SIZE_BYTES 必须是整数") from exc
    if value <= 0:
        raise RuntimeError("MAX_UPLOAD_SIZE_BYTES 必须大于 0")
    return value


def calculate_checksum(stream: BinaryIO) -> str:
    digest = hashlib.sha256()
    stream.seek(0)
    while chunk := stream.read(1024 * 1024):
        digest.update(chunk)
    stream.seek(0)
    return digest.hexdigest()


def _validate_signature(extension: str, header: bytes) -> None:
    if extension == ".pdf" and not header.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="PDF 文件内容与扩展名不一致")
    if extension == ".docx" and not header.startswith(b"PK"):
        raise HTTPException(status_code=400, detail="DOCX 文件内容与扩展名不一致")
    if extension == ".txt" and b"\x00" in header:
        raise HTTPException(status_code=400, detail="TXT 文件包含二进制内容")


def prepare_upload(upload: UploadFile, size_limit: int | None = None) -> PreparedUpload:
    original = Path(upload.filename or "").name.strip()
    extension = Path(original).suffix.lower()
    expected_mime = ALLOWED_FILE_TYPES.get(extension)
    if not original or expected_mime is None:
        raise HTTPException(status_code=400, detail="仅支持 PDF、DOCX 和 TXT 文件")

    supplied_mime = (upload.content_type or "").split(";", 1)[0].strip().lower()
    if supplied_mime != expected_mime:
        raise HTTPException(
            status_code=400,
            detail=f"文件扩展名与 MIME 类型不一致：{extension} 应为 {expected_mime}",
        )

    limit = size_limit if size_limit is not None else max_upload_size()
    buffered = tempfile.SpooledTemporaryFile(max_size=min(limit, 4 * 1024 * 1024), mode="w+b")
    total = 0
    digest = hashlib.sha256()
    header = b""
    try:
        upload.file.seek(0)
        while chunk := upload.file.read(1024 * 1024):
            total += len(chunk)
            if total > limit:
                raise HTTPException(status_code=413, detail=f"文件超过大小限制（最大 {limit} 字节）")
            if len(header) < 4096:
                header += chunk[: 4096 - len(header)]
            digest.update(chunk)
            buffered.write(chunk)
        if total == 0:
            raise HTTPException(status_code=400, detail="不能上传空文件")
        _validate_signature(extension, header)
        buffered.seek(0)
        return PreparedUpload(
            original_filename=original,
            safe_filename=safe_filename(original),
            file_type=extension.lstrip("."),
            mime_type=expected_mime,
            file_size=total,
            checksum=digest.hexdigest(),
            stream=buffered,
        )
    except Exception:
        buffered.close()
        raise
