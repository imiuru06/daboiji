"""S3-compatible object storage (AWS S3, R2, MinIO, …) via boto3.

Config: DABWAYO_STORAGE_S3_BUCKET (required), DABWAYO_STORAGE_S3_PREFIX (opt),
DABWAYO_STORAGE_S3_ENDPOINT (opt, for R2/MinIO), plus standard AWS credentials.
Downloads are cached under DABWAYO_STORAGE_CACHE (default .vf_cache).
"""
from __future__ import annotations

import os
from typing import Optional

from .base import StorageProvider, StorageError


class S3Storage(StorageProvider):
    name = "s3"

    def _cfg(self):
        return (os.environ.get("DABWAYO_STORAGE_S3_BUCKET", ""),
                os.environ.get("DABWAYO_STORAGE_S3_PREFIX", "").strip("/"),
                os.environ.get("DABWAYO_STORAGE_S3_ENDPOINT", "") or None)

    def available(self) -> tuple[bool, str]:
        bucket, _, _ = self._cfg()
        if not bucket:
            return (False, "set DABWAYO_STORAGE_S3_BUCKET")
        try:
            import boto3  # noqa: F401
            return (True, f"bucket {bucket}")
        except ImportError:
            return (False, "pip install boto3")

    def _client(self):
        try:
            import boto3
        except ImportError as e:  # pragma: no cover
            raise StorageError("pip install boto3") from e
        _, _, endpoint = self._cfg()
        return boto3.client("s3", endpoint_url=endpoint)

    def _parse(self, uri: str):
        rest = uri[len("s3://"):]
        bucket, _, key = rest.partition("/")
        return bucket, key

    def put(self, local_path: str, key: Optional[str] = None) -> str:
        bucket, prefix, _ = self._cfg()
        if not bucket:
            raise StorageError("set DABWAYO_STORAGE_S3_BUCKET")
        key = key or os.path.basename(local_path)
        if prefix:
            key = f"{prefix}/{key}"
        try:
            self._client().upload_file(local_path, bucket, key)
        except Exception as e:  # noqa: BLE001
            raise StorageError(f"s3 upload failed: {e}") from e
        return f"s3://{bucket}/{key}"

    def localize(self, uri: str) -> str:
        bucket, key = self._parse(uri)
        cache = os.environ.get("DABWAYO_STORAGE_CACHE", ".vf_cache")
        os.makedirs(cache, exist_ok=True)
        dest = os.path.join(cache, os.path.basename(key))
        if not os.path.isfile(dest):
            try:
                self._client().download_file(bucket, key, dest)
            except Exception as e:  # noqa: BLE001
                raise StorageError(f"s3 download failed: {e}") from e
        return dest

    def url(self, uri: str) -> Optional[str]:
        bucket, key = self._parse(uri)
        try:
            return self._client().generate_presigned_url(
                "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=3600)
        except Exception:  # noqa: BLE001
            return None

    def exists(self, uri: str) -> bool:
        bucket, key = self._parse(uri)
        try:
            self._client().head_object(Bucket=bucket, Key=key)
            return True
        except Exception:  # noqa: BLE001
            return False
