from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(slots=True)
class PixabayImageHit:
    item_id: str
    preview_url: str
    download_url: str
    width: int
    height: int
    size_bytes: int | None
    fallback_urls: list[str]


@dataclass(slots=True)
class PixabayVideoHit:
    item_id: str
    preview_url: str
    download_url: str
    width: int
    height: int
    duration: int
    size_bytes: int | None
    rendition: str
    fallback_urls: list[str]


class MediaDownloadError(RuntimeError):
    pass


class PixabayClient:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def search_images(self, *, query: str, categories: list[str], safesearch: bool, per_page: int) -> list[PixabayImageHit]:
        params = {
            "key": self._api_key,
            "q": query,
            "safesearch": "true" if safesearch else "false",
            "per_page": str(per_page),
            "category": categories[0] if categories else "",
        }
        data = self._get_json("https://pixabay.com/api/", params)
        hits: list[PixabayImageHit] = []
        for item in data.get("hits", []):
            large_url = str(item.get("largeImageURL") or "")
            webformat_url = str(item.get("webformatURL") or "")
            preview_url = str(item.get("previewURL") or "")
            fallback_urls = [url for url in [webformat_url, preview_url] if url]
            hits.append(
                PixabayImageHit(
                    item_id=str(item.get("id")),
                    preview_url=preview_url,
                    download_url=large_url or webformat_url or preview_url,
                    width=int(item.get("imageWidth") or 0),
                    height=int(item.get("imageHeight") or 0),
                    size_bytes=int(item.get("imageSize")) if item.get("imageSize") else None,
                    fallback_urls=fallback_urls,
                )
            )
        return [hit for hit in hits if hit.download_url]

    def search_videos(
        self,
        *,
        query: str,
        categories: list[str],
        safesearch: bool,
        per_page: int,
        preferred_renditions: list[str],
        forbidden_renditions: list[str],
    ) -> list[PixabayVideoHit]:
        params = {
            "key": self._api_key,
            "q": query,
            "safesearch": "true" if safesearch else "false",
            "per_page": str(per_page),
            "category": categories[0] if categories else "",
        }
        data = self._get_json("https://pixabay.com/api/videos/", params)
        results: list[PixabayVideoHit] = []
        for item in data.get("hits", []):
            videos = item.get("videos") or {}
            selected = None
            fallback_urls: list[str] = []
            for rendition in preferred_renditions:
                candidate = videos.get(rendition)
                if candidate and rendition not in forbidden_renditions:
                    selected = (rendition, candidate)
                    break
            if selected is None:
                for rendition, candidate in videos.items():
                    if rendition in forbidden_renditions:
                        continue
                    selected = (rendition, candidate)
                    break
            if selected is None:
                continue
            rendition, candidate = selected
            for fallback_name in preferred_renditions:
                alt = videos.get(fallback_name)
                if not alt or fallback_name == rendition or fallback_name in forbidden_renditions:
                    continue
                alt_url = str(alt.get("url") or "")
                if alt_url:
                    fallback_urls.append(alt_url)
            results.append(
                PixabayVideoHit(
                    item_id=str(item.get("id")),
                    preview_url=str(item.get("picture_id") or ""),
                    download_url=str(candidate.get("url") or ""),
                    width=int(candidate.get("width") or 0),
                    height=int(candidate.get("height") or 0),
                    duration=int(item.get("duration") or 0),
                    size_bytes=int(candidate.get("size")) if candidate.get("size") else None,
                    rendition=rendition,
                    fallback_urls=fallback_urls,
                )
            )
        return [item for item in results if item.download_url]

    def download_file(self, *, url: str, dest_path: Path, fallback_urls: list[str] | None = None) -> int:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        candidates = [url, *(fallback_urls or [])]
        last_error: Exception | None = None
        headers = {
            "User-Agent": "Mozilla/5.0 (NerdexDemoSeed/1.0)",
            "Accept": "*/*",
            "Referer": "https://pixabay.com/",
        }
        for candidate_url in candidates:
            if not candidate_url:
                continue
            request = Request(candidate_url, headers=headers)
            try:
                with urlopen(request, timeout=60) as response:
                    payload = response.read()
                dest_path.write_bytes(payload)
                return len(payload)
            except (HTTPError, URLError, TimeoutError) as exc:
                last_error = exc
                if dest_path.exists():
                    dest_path.unlink()
                continue
        raise MediaDownloadError(f"Failed to download media after trying {len(candidates)} URL(s)") from last_error

    def _get_json(self, base_url: str, params: dict[str, str]) -> dict:
        query = urlencode(params)
        url = f"{base_url}?{query}"
        request = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (NerdexDemoSeed/1.0)",
                "Accept": "application/json",
                "Referer": "https://pixabay.com/",
            },
        )
        with urlopen(request, timeout=30) as response:
            payload = response.read()
        return json.loads(payload.decode("utf-8"))
