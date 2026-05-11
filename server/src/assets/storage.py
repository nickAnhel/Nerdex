from __future__ import annotations

import hashlib
import mimetypes
import uuid
from pathlib import Path
from contextlib import asynccontextmanager
from dataclasses import dataclass
from urllib.parse import quote

from botocore.config import Config
from botocore.exceptions import ClientError

from src.assets.enums import AssetVariantTypeEnum
from src.config import StorageSettings

import aiofiles

try:
    from aiobotocore.session import get_session
except ModuleNotFoundError:  # pragma: no cover - exercised in lightweight unit-test envs
    get_session = None


IMAGE_EXTENSION_TO_MIME = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "gif": "image/gif",
}


@dataclass(slots=True)
class ObjectHead:
    bucket: str
    key: str
    size_bytes: int
    mime_type: str | None
    etag: str | None


@dataclass(slots=True)
class UploadInstruction:
    bucket: str
    key: str
    url: str
    headers: dict[str, str]
    expires_in_seconds: int


@dataclass(slots=True)
class StoredObject:
    size_bytes: int
    checksum_sha256: str
    mime_type: str
    width: int | None = None
    height: int | None = None
    duration_ms: int | None = None
    bitrate: int | None = None


class AssetStorage:
    def __init__(self, settings: StorageSettings) -> None:
        self._settings = settings
        self._session = None if get_session is None else get_session()
        endpoint_url = settings.resolved_endpoint_url
        self._client_config = {
            "aws_access_key_id": settings.access_key,
            "aws_secret_access_key": settings.secret_key,
            "endpoint_url": endpoint_url,
            "region_name": settings.region,
            "use_ssl": settings.use_ssl,
            "config": Config(
                signature_version="s3v4",
                s3={"addressing_style": settings.addressing_style},
            ),
        }

    @property
    def private_bucket(self) -> str:
        return self._settings.private_bucket

    @asynccontextmanager
    async def _client(self):  # type: ignore[no-untyped-def]
        if self._session is None:
            raise RuntimeError("aiobotocore is required to use AssetStorage")
        async with self._session.create_client(
            "s3",
            **self._client_config,
            verify=self._settings.verify_ssl,
        ) as client:
            yield client

    async def generate_presigned_put(
        self,
        *,
        bucket: str,
        key: str,
        mime_type: str | None,
    ) -> UploadInstruction:
        headers = {}
        params: dict[str, str] = {"Bucket": bucket, "Key": key}
        if mime_type:
            params["ContentType"] = mime_type
            headers["Content-Type"] = mime_type

        async with self._client() as client:
            url = await client.generate_presigned_url(
                "put_object",
                Params=params,
                ExpiresIn=self._settings.presigned_upload_ttl_seconds,
            )

        return UploadInstruction(
            bucket=bucket,
            key=key,
            url=url,
            headers=headers,
            expires_in_seconds=self._settings.presigned_upload_ttl_seconds,
        )

    async def generate_presigned_get(
        self,
        *,
        bucket: str,
        key: str,
        download_filename: str | None = None,
        inline: bool = True,
        response_content_type: str | None = None,
    ) -> str:
        params: dict[str, str] = {"Bucket": bucket, "Key": key}
        if download_filename:
            disposition = "inline" if inline else "attachment"
            params["ResponseContentDisposition"] = (
                f"{disposition}; filename*=UTF-8''{quote(download_filename)}"
            )
        if response_content_type:
            params["ResponseContentType"] = response_content_type

        async with self._client() as client:
            return await client.generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=self._settings.presigned_download_ttl_seconds,
            )

    async def head_object(
        self,
        *,
        bucket: str,
        key: str,
    ) -> ObjectHead | None:
        try:
            async with self._client() as client:
                response = await client.head_object(Bucket=bucket, Key=key)
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                return None
            return None

        return ObjectHead(
            bucket=bucket,
            key=key,
            size_bytes=response["ContentLength"],
            mime_type=response.get("ContentType"),
            etag=response.get("ETag"),
        )

    async def get_object_bytes(
        self,
        *,
        bucket: str,
        key: str,
    ) -> bytes:
        async with self._client() as client:
            response = await client.get_object(Bucket=bucket, Key=key)
            body = response["Body"]
            return await body.read()

    async def download_to_file(
        self,
        *,
        bucket: str,
        key: str,
        path: Path,
        chunk_size: int = 1024 * 1024,
    ) -> None:
        async with self._client() as client:
            response = await client.get_object(Bucket=bucket, Key=key)
            body = response["Body"]
            async with aiofiles.open(path, "wb") as file:
                while True:
                    chunk = await body.read(chunk_size)
                    if not chunk:
                        break
                    await file.write(chunk)

    async def upload_bytes(
        self,
        *,
        bucket: str,
        key: str,
        payload: bytes,
        mime_type: str,
    ) -> StoredObject:
        async with self._client() as client:
            await client.put_object(
                Bucket=bucket,
                Key=key,
                Body=payload,
                ContentType=mime_type,
            )

        return StoredObject(
            size_bytes=len(payload),
            checksum_sha256=hashlib.sha256(payload).hexdigest(),
            mime_type=mime_type,
        )

    async def upload_file(
        self,
        *,
        bucket: str,
        key: str,
        path: Path,
        mime_type: str,
    ) -> StoredObject:
        checksum = hashlib.sha256()
        async with aiofiles.open(path, "rb") as file:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                checksum.update(chunk)

        with path.open("rb") as body:
            async with self._client() as client:
                await client.put_object(
                    Bucket=bucket,
                    Key=key,
                    Body=body,
                    ContentType=mime_type,
                )

        return StoredObject(
            size_bytes=path.stat().st_size,
            checksum_sha256=checksum.hexdigest(),
            mime_type=mime_type,
        )

    async def delete_object(
        self,
        *,
        bucket: str,
        key: str,
    ) -> None:
        async with self._client() as client:
            await client.delete_object(Bucket=bucket, Key=key)

    async def initiate_multipart_upload(
        self,
        *,
        bucket: str,
        key: str,
        mime_type: str | None,
    ) -> str:
        params = {"Bucket": bucket, "Key": key}
        if mime_type:
            params["ContentType"] = mime_type

        async with self._client() as client:
            response = await client.create_multipart_upload(**params)
            return response["UploadId"]

    async def complete_multipart_upload(
        self,
        *,
        bucket: str,
        key: str,
        upload_id: str,
        parts: list[dict[str, str | int]],
    ) -> None:
        async with self._client() as client:
            await client.complete_multipart_upload(
                Bucket=bucket,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )

    async def abort_multipart_upload(
        self,
        *,
        bucket: str,
        key: str,
        upload_id: str,
    ) -> None:
        async with self._client() as client:
            await client.abort_multipart_upload(
                Bucket=bucket,
                Key=key,
                UploadId=upload_id,
            )


def detect_extension(filename: str) -> str | None:
    if "." not in filename:
        return None

    return filename.rsplit(".", 1)[1].lower()


def guess_mime_type(filename: str, declared_mime_type: str | None = None) -> str | None:
    extension = detect_extension(filename)
    if extension in IMAGE_EXTENSION_TO_MIME:
        return IMAGE_EXTENSION_TO_MIME[extension]
    if declared_mime_type:
        return declared_mime_type
    return mimetypes.guess_type(filename)[0]


def build_asset_storage_key(
    *,
    asset_id: uuid.UUID,
    variant_type: AssetVariantTypeEnum,
    extension: str,
) -> str:
    normalized_extension = extension.lower().lstrip(".")
    return (
        f"v1/assets/{asset_id.hex[:2]}/{asset_id}/{variant_type.value}.{normalized_extension}"
    )
