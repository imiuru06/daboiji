"""Google Cloud Storage backend via google-cloud-storage.

Config: DABWAYO_STORAGE_GCS_BUCKET (required), DABWAYO_STORAGE_GCS_PREFIX (opt),
plus standard GCP credentials (GOOGLE_APPLICATION_CREDENTIALS). Downloads are
cached under DABWAYO_STORAGE_CACHE (default .vf_cache).

(Cloudflare R2 / MinIO / any S3-compatible store already work via the ``s3``
backend with DABWAYO_STORAGE_S3_ENDPOINT — this adds native GCS.)
"""
from __future__ import annotations

import os
from typing import Optional

from .base import StorageProvider, StorageError


class GCSStorage(StorageProvider):
    name = "gcs"

    def _cfg(self):
        return (os.environ.get("DABWAYO_STORAGE_GCS_BUCKET", ""),
                os.environ.get("DABWAYO_STORAGE_GCS_PREFIX", "").strip("/"))

    def available(self) -> tuple[bool, str]:
        bucket, _ = self._cfg()
        if not bucket:
            return (False, "set DABWAYO_STORAGE_GCS_BUCKET")
        try:
            import google.cloud.storage  # noqa: F401
            return (True, f"bucket {bucket}")
        except ImportError:
            return (False, "pip install google-cloud-storage")

    def _bucket(self):
        try:
            from google.cloud import storage
        except ImportError as e:  # pragma: no cover
            raise StorageError("pip install google-cloud-storage") from e
        name, _ = self._cfg()
        return storage.Client().bucket(name)

    def _parse(self, uri: str):
        rest = uri[len("gs://"):]
        bucket, _, key = rest.partition("/")
        return bucket, key

    def put(self, local_path: str, key: Optional[str] = None) -> str:
        bucket_name, prefix = self._cfg()
        if not bucket_name:
            raise StorageError("set DABWAYO_STORAGE_GCS_BUCKET")
        key = key or os.path.basename(local_path)
        if prefix:
            key = f"{prefix}/{key}"
        try:
            self._bucket().blob(key).upload_from_filename(local_path)
        except Exception as e:  # noqa: BLE001
            raise StorageError(f"gcs upload failed: {e}") from e
        return f"gs://{bucket_name}/{key}"

    def localize(self, uri: str) -> str:
        _, key = self._parse(uri)
        cache = os.environ.get("DABWAYO_STORAGE_CACHE", ".vf_cache")
        os.makedirs(cache, exist_ok=True)
        dest = os.path.join(cache, os.path.basename(key))
        if not os.path.isfile(dest):
            try:
                self._bucket().blob(key).download_to_filename(dest)
            except Exception as e:  # noqa: BLE001
                raise StorageError(f"gcs download failed: {e}") from e
        return dest

    def url(self, uri: str) -> Optional[str]:
        _, key = self._parse(uri)
        try:
            import datetime
            return self._bucket().blob(key).generate_signed_url(
                expiration=datetime.timedelta(hours=1))
        except Exception:  # noqa: BLE001
            return None

    def exists(self, uri: str) -> bool:
        _, key = self._parse(uri)
        try:
            return self._bucket().blob(key).exists()
        except Exception:  # noqa: BLE001
            return False
