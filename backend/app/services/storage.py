from __future__ import annotations

import os
import re
import shutil
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Optional


class StorageError(RuntimeError):
    """A safe, provider-independent storage failure."""


class StorageConfigurationError(StorageError):
    """Storage environment variables are missing or invalid."""


class StorageObjectNotFound(StorageError):
    """The requested object does not exist."""


class StorageService(ABC):
    provider_name: str

    @abstractmethod
    def put(self, key: str, source: BinaryIO, content_type: str) -> str:
        """Store source at key and return the persisted key."""

    @abstractmethod
    def download_to_temp(self, key: str, suffix: str = "") -> Path:
        """Download an object to a caller-owned temporary file."""

    @abstractmethod
    def open_stream(self, key: str) -> BinaryIO:
        """Open an object for streaming reads."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete an object. Missing objects are treated as already deleted."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Return whether an object exists."""

    @abstractmethod
    def create_presigned_download_url(self, key: str, expires_in: int = 300) -> Optional[str]:
        """Return a short-lived download URL when supported by the provider."""


def safe_filename(filename: str) -> str:
    name = Path(filename or "document").name
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()
    name = re.sub(r"[\\/:*?\"<>|]+", "_", name)
    name = re.sub(r"\s+", "_", name)
    if name in {"", ".", ".."}:
        name = "document"
    stem = Path(name).stem[:160] or "document"
    suffix = Path(name).suffix.lower()[:16]
    return f"{stem}{suffix}"


def build_object_key(case_id: int, document_id: int, checksum: str, filename: str) -> str:
    digest = re.sub(r"[^0-9a-f]", "", checksum.lower())
    if len(digest) != 64:
        raise StorageError("文件校验值格式无效")
    return f"cases/{case_id}/documents/{document_id}/{digest}-{safe_filename(filename)}"


def _validate_object_key(key: str) -> str:
    normalized = str(PurePosixPath(key))
    path = PurePosixPath(normalized)
    if not key or key.startswith(("/", "\\")) or ".." in path.parts or normalized in {".", ".."}:
        raise StorageError("对象键不安全")
    return normalized


class LocalStorageService(StorageService):
    provider_name = "local"

    def __init__(self, root: Path | str):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        normalized = _validate_object_key(key)
        target = (self.root / Path(*PurePosixPath(normalized).parts)).resolve()
        try:
            target.relative_to(self.root)
        except ValueError as exc:
            raise StorageError("对象键越出存储目录") from exc
        return target

    def put(self, key: str, source: BinaryIO, content_type: str) -> str:
        del content_type
        target = self._path_for(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.uploading")
        try:
            source.seek(0)
            with temporary.open("wb") as output:
                shutil.copyfileobj(source, output)
            temporary.replace(target)
        except Exception as exc:
            temporary.unlink(missing_ok=True)
            raise StorageError("本地文件存储失败") from exc
        return key

    def download_to_temp(self, key: str, suffix: str = "") -> Path:
        source = self._path_for(key)
        if not source.is_file():
            raise StorageObjectNotFound("原始文件不存在")
        handle = tempfile.NamedTemporaryFile(prefix="lexflow-", suffix=suffix, delete=False)
        target = Path(handle.name)
        try:
            with handle, source.open("rb") as input_file:
                shutil.copyfileobj(input_file, handle)
        except Exception as exc:
            target.unlink(missing_ok=True)
            raise StorageError("读取本地文件失败") from exc
        return target

    def open_stream(self, key: str) -> BinaryIO:
        target = self._path_for(key)
        if not target.is_file():
            raise StorageObjectNotFound("原始文件不存在")
        return target.open("rb")

    def delete(self, key: str) -> None:
        target = self._path_for(key)
        target.unlink(missing_ok=True)
        parent = target.parent
        while parent != self.root:
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent

    def exists(self, key: str) -> bool:
        return self._path_for(key).is_file()

    def create_presigned_download_url(self, key: str, expires_in: int = 300) -> Optional[str]:
        del key, expires_in
        return None


class S3CompatibleStorageService(StorageService):
    def __init__(
        self,
        *,
        bucket_name: str,
        endpoint_url: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        region: str = "auto",
        provider_name: str = "s3",
        client=None,
    ):
        if not bucket_name:
            raise StorageConfigurationError("缺少 S3_BUCKET_NAME")
        self.bucket_name = bucket_name
        self.provider_name = provider_name
        if client is None:
            try:
                import boto3
            except ImportError as exc:
                raise StorageConfigurationError("S3 存储依赖尚未安装") from exc
            client = boto3.client(
                "s3",
                endpoint_url=endpoint_url or None,
                aws_access_key_id=access_key_id or None,
                aws_secret_access_key=secret_access_key or None,
                region_name=region or "auto",
            )
        self.client = client

    def put(self, key: str, source: BinaryIO, content_type: str) -> str:
        normalized = _validate_object_key(key)
        try:
            source.seek(0)
            self.client.upload_fileobj(
                source,
                self.bucket_name,
                normalized,
                ExtraArgs={"ContentType": content_type},
            )
        except Exception as exc:
            raise StorageError("对象存储上传失败") from exc
        return normalized

    def download_to_temp(self, key: str, suffix: str = "") -> Path:
        normalized = _validate_object_key(key)
        handle = tempfile.NamedTemporaryFile(prefix="lexflow-", suffix=suffix, delete=False)
        target = Path(handle.name)
        handle.close()
        try:
            self.client.download_file(self.bucket_name, normalized, str(target))
        except Exception as exc:
            target.unlink(missing_ok=True)
            raise StorageError("对象存储下载失败") from exc
        return target

    def open_stream(self, key: str) -> BinaryIO:
        normalized = _validate_object_key(key)
        try:
            return self.client.get_object(Bucket=self.bucket_name, Key=normalized)["Body"]
        except Exception as exc:
            raise StorageObjectNotFound("原始文件不存在") from exc

    def delete(self, key: str) -> None:
        normalized = _validate_object_key(key)
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=normalized)
        except Exception as exc:
            raise StorageError("对象存储删除失败") from exc

    def exists(self, key: str) -> bool:
        normalized = _validate_object_key(key)
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=normalized)
            return True
        except Exception as exc:
            response = getattr(exc, "response", {}) or {}
            status = (response.get("ResponseMetadata") or {}).get("HTTPStatusCode")
            code = str((response.get("Error") or {}).get("Code", ""))
            if status == 404 or code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise StorageError("对象存储状态检查失败") from exc

    def create_presigned_download_url(self, key: str, expires_in: int = 300) -> Optional[str]:
        normalized = _validate_object_key(key)
        expires = max(60, min(int(expires_in), 3600))
        try:
            return self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": normalized},
                ExpiresIn=expires,
            )
        except Exception as exc:
            raise StorageError("下载地址生成失败") from exc


def get_storage_service(provider: Optional[str] = None) -> StorageService:
    configured_provider = provider or os.getenv("STORAGE_PROVIDER")
    if not configured_provider and os.getenv("RENDER"):
        raise StorageConfigurationError("Render 环境必须显式配置 STORAGE_PROVIDER")
    provider = (configured_provider or "local").strip().lower()
    if provider in {"local", "filesystem"}:
        root = os.getenv("UPLOAD_DIR") or str(Path(__file__).resolve().parents[1] / "uploads")
        return LocalStorageService(root)
    if provider not in {"s3", "r2"}:
        raise StorageConfigurationError("STORAGE_PROVIDER 仅支持 local、s3 或 r2")
    return S3CompatibleStorageService(
        bucket_name=os.getenv("S3_BUCKET_NAME", "").strip(),
        endpoint_url=os.getenv("S3_ENDPOINT_URL", "").strip() or None,
        access_key_id=os.getenv("S3_ACCESS_KEY_ID", "").strip() or None,
        secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY", "").strip() or None,
        region=os.getenv("S3_REGION", "auto").strip() or "auto",
        provider_name=provider,
    )
