from __future__ import annotations

import hashlib
from pathlib import Path

from src.assets.storage import AssetStorage, StoredObject


async def upload_path_to_s3(storage: AssetStorage, *, local_path: Path, key: str, mime_type: str) -> StoredObject:
    return await storage.upload_file(
        bucket=storage.private_bucket,
        key=key,
        path=local_path,
        mime_type=mime_type,
    )


async def upload_bytes_to_s3(storage: AssetStorage, *, payload: bytes, key: str, mime_type: str) -> StoredObject:
    return await storage.upload_bytes(
        bucket=storage.private_bucket,
        key=key,
        payload=payload,
        mime_type=mime_type,
    )


def guess_extension(mime_type: str, default: str = "bin") -> str:
    if "/" not in mime_type:
        return default
    subtype = mime_type.split("/", 1)[1].split(";")[0].strip().lower()
    if subtype == "jpeg":
        return "jpg"
    if subtype == "plain":
        return "txt"
    if subtype == "markdown":
        return "md"
    if subtype == "yaml":
        return "yml"
    return subtype or default


def checksum_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
