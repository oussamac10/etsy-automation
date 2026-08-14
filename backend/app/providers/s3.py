from __future__ import annotations

import asyncio
import hashlib
from typing import Any
import boto3
from botocore.config import Config

from app.ports.errors import ProviderError, ProviderErrorKind
from app.ports.providers import StoredObject


class S3ObjectStorage:
    """Real ObjectStorage adapter wrapping boto3 client calls.

    MinIO is used locally. We use path-style addressing config for local MinIO
    compatibility. All network operations are run in an executor thread via
    asyncio.to_thread to prevent blocking the async loop.
    """

    def __init__(
        self,
        endpoint_url: str,
        bucket_name: str,
        access_key_id: str,
        secret_access_key: str,
        region_name: str = "us-east-1",
        force_path_style: bool = True,
        public_endpoint_url: str | None = None,
    ) -> None:
        self._endpoint_url = endpoint_url
        self._bucket_name = bucket_name
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._region_name = region_name
        self._public_endpoint_url = public_endpoint_url

        # MinIO/local S3 services generally require force_path_style=True
        self._config = Config(
            s3={"addressing_style": "path" if force_path_style else "auto"},
            signature_version="s3v4",
        )

    def _get_client(self) -> Any:
        return boto3.client(
            "s3",
            endpoint_url=self._endpoint_url,
            aws_access_key_id=self._access_key_id,
            aws_secret_access_key=self._secret_access_key,
            region_name=self._region_name,
            config=self._config,
        )

    async def put(self, key: str, data: bytes, content_type: str) -> StoredObject:
        try:
            client = self._get_client()
            # Run blocking boto3 client calls in a background thread
            await asyncio.to_thread(
                client.put_object,
                Bucket=self._bucket_name,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
            sha256 = hashlib.sha256(data).hexdigest()
            return StoredObject(
                storage_key=key,
                sha256=sha256,
                byte_size=len(data),
                content_type=content_type,
            )
        except Exception as exc:
            raise ProviderError(
                kind=ProviderErrorKind.RETRYABLE,
                provider="s3",
                operation="put",
                message=f"Failed to upload object to S3: {exc!s}",
            ) from exc

    async def get(self, key: str) -> bytes:
        try:
            client = self._get_client()
            response = await asyncio.to_thread(
                client.get_object,
                Bucket=self._bucket_name,
                Key=key,
            )
            body = response["Body"]
            data = await asyncio.to_thread(body.read)
            assert isinstance(data, bytes)
            return data
        except Exception as exc:
            raise ProviderError(
                kind=ProviderErrorKind.INVALID_REQUEST,
                provider="s3",
                operation="get",
                message=f"Failed to retrieve object from S3: {exc!s}",
            ) from exc

    async def signed_url(self, key: str, expires_in_seconds: int) -> str:
        try:
            client = self._get_client()
            url = await asyncio.to_thread(
                client.generate_presigned_url,
                ClientMethod="get_object",
                Params={
                    "Bucket": self._bucket_name,
                    "Key": key,
                },
                ExpiresIn=expires_in_seconds,
            )
            assert isinstance(url, str)
            if self._public_endpoint_url and self._endpoint_url in url:
                url = url.replace(self._endpoint_url, self._public_endpoint_url)
            return url
        except Exception as exc:
            raise ProviderError(
                kind=ProviderErrorKind.RETRYABLE,
                provider="s3",
                operation="signed_url",
                message=f"Failed to generate presigned S3 URL: {exc!s}",
            ) from exc
