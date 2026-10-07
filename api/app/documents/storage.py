"""Private object storage over the standard S3 protocol (works with real S3 or any S3-compatible
store). Objects get random keys; the user's file name is never part of a storage path."""

from collections.abc import Iterator
from typing import BinaryIO, Protocol

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError


class StorageUnavailableError(Exception):
    """The store could not complete the operation. Nothing may be assumed saved."""


class ObjectStorage(Protocol):
    def put(self, key: str, file: BinaryIO, size: int) -> None: ...

    def get(self, key: str) -> Iterator[bytes]: ...

    def delete(self, key: str) -> None: ...


class S3Storage:
    def __init__(
        self,
        *,
        endpoint_url: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        region: str = "us-east-1",
    ) -> None:
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(
                s3={"addressing_style": "path"},
                retries={"max_attempts": 2},
                connect_timeout=5,
                read_timeout=60,
            ),
        )

    def ensure_bucket(self) -> None:
        """Create the bucket if missing (local and tests; real environments provision it)."""
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError:
            self._client.create_bucket(Bucket=self._bucket)

    def put(self, key: str, file: BinaryIO, size: int) -> None:
        file.seek(0)
        try:
            self._client.put_object(Bucket=self._bucket, Key=key, Body=file, ContentLength=size)
        except (BotoCoreError, ClientError):
            raise StorageUnavailableError from None

    def get(self, key: str) -> Iterator[bytes]:
        try:
            body = self._client.get_object(Bucket=self._bucket, Key=key)["Body"]
        except (BotoCoreError, ClientError):
            raise StorageUnavailableError from None
        try:
            yield from body.iter_chunks(chunk_size=64 * 1024)
        finally:
            body.close()

    def delete(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except (BotoCoreError, ClientError):
            raise StorageUnavailableError from None
