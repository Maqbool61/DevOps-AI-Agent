"""Storage factory — selects backend from environment."""
from __future__ import annotations

import os
from functools import lru_cache

from storage.base import StorageProvider
from storage.memory_storage import MemoryStorage


@lru_cache(maxsize=1)
def get_storage() -> StorageProvider:
    provider = os.getenv("STORAGE_PROVIDER", "memory").lower().strip()

    if provider in ("memory", "local", ""):
        return MemoryStorage()

    bucket = os.getenv("STORAGE_BUCKET", os.getenv("STORAGE_CONTAINER", "devops-agent"))

    if provider in ("s3", "aws"):
        from storage.s3_storage import S3Storage
        return S3Storage(
            bucket=bucket,
            region=os.getenv("AWS_REGION"),
            endpoint_url=None,
        )

    if provider in ("minio", "s3-compatible"):
        from storage.s3_storage import S3Storage
        return S3Storage(
            bucket=bucket,
            region=os.getenv("AWS_REGION", "us-east-1"),
            endpoint_url=os.getenv("STORAGE_ENDPOINT_URL", os.getenv("MINIO_ENDPOINT")),
            access_key=os.getenv("STORAGE_ACCESS_KEY", os.getenv("MINIO_ACCESS_KEY")),
            secret_key=os.getenv("STORAGE_SECRET_KEY", os.getenv("MINIO_SECRET_KEY")),
        )

    if provider in ("gcs", "gcp", "google"):
        from storage.gcs_storage import GCSStorage
        return GCSStorage(bucket=bucket, project=os.getenv("GCP_PROJECT_ID"))

    if provider in ("azure", "blob"):
        from storage.azure_storage import AzureBlobStorage
        return AzureBlobStorage(
            container=bucket,
            connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
            account_url=os.getenv("AZURE_STORAGE_ACCOUNT_URL"),
        )

    raise ValueError(
        f"Unknown STORAGE_PROVIDER={provider!r}. "
        "Use: memory, s3, minio, gcs, azure"
    )
