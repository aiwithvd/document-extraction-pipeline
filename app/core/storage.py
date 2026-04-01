import asyncio
from functools import partial
from io import BytesIO

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import settings
from app.utils.exceptions import StorageError


class StorageClient:
    def __init__(self) -> None:
        self._client = boto3.client(
            "s3",
            endpoint_url=f"{'https' if settings.MINIO_USE_SSL else 'http'}://{settings.MINIO_ENDPOINT}",
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
        self._bucket = settings.MINIO_BUCKET

    def _upload_sync(self, file_bytes: bytes, object_key: str, content_type: str) -> None:
        self._client.put_object(
            Bucket=self._bucket,
            Key=object_key,
            Body=file_bytes,
            ContentType=content_type,
        )

    def _download_sync(self, object_key: str) -> bytes:
        buf = BytesIO()
        self._client.download_fileobj(self._bucket, object_key, buf)
        return buf.getvalue()

    def _presign_sync(self, object_key: str, expiry: int) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": object_key},
            ExpiresIn=expiry,
        )

    def _delete_sync(self, object_key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=object_key)

    def _check_bucket_sync(self) -> bool:
        try:
            self._client.head_bucket(Bucket=self._bucket)
            return True
        except ClientError:
            return False

    async def upload_file(self, file_bytes: bytes, object_key: str, content_type: str) -> str:
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(
                None, partial(self._upload_sync, file_bytes, object_key, content_type)
            )
        except ClientError as exc:
            raise StorageError(f"Upload failed for {object_key}: {exc}") from exc
        return object_key

    async def download_file(self, object_key: str) -> bytes:
        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(
                None, partial(self._download_sync, object_key)
            )
        except ClientError as exc:
            raise StorageError(f"Download failed for {object_key}: {exc}") from exc

    async def generate_presigned_url(self, object_key: str, expiry: int = 3600) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, partial(self._presign_sync, object_key, expiry)
        )

    async def delete_file(self, object_key: str) -> None:
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, partial(self._delete_sync, object_key))
        except ClientError as exc:
            raise StorageError(f"Delete failed for {object_key}: {exc}") from exc

    async def check_connectivity(self) -> bool:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._check_bucket_sync)


storage_client = StorageClient()
