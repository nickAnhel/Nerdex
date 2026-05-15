from __future__ import annotations

from pathlib import Path


class FakeStoredObject:
    def __init__(self, size_bytes: int, mime_type: str) -> None:
        self.size_bytes = size_bytes
        self.checksum_sha256 = "deadbeef"
        self.mime_type = mime_type
        self.width = None
        self.height = None
        self.duration_ms = None
        self.bitrate = None


class FakeStorage:
    def __init__(self) -> None:
        self.private_bucket = "test-private"
        self.uploaded: list[tuple[str, str, int]] = []

    async def upload_bytes(self, *, bucket: str, key: str, payload: bytes, mime_type: str):
        self.uploaded.append((bucket, key, len(payload)))
        return FakeStoredObject(size_bytes=len(payload), mime_type=mime_type)

    async def upload_file(self, *, bucket: str, key: str, path: Path, mime_type: str):
        size = path.stat().st_size
        self.uploaded.append((bucket, key, size))
        return FakeStoredObject(size_bytes=size, mime_type=mime_type)

    async def delete_object(self, *, bucket: str, key: str):
        self.uploaded.append((bucket, key, -1))
        return None
