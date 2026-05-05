from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

from src.assets.enums import AssetVariantTypeEnum
from src.videos.enums import VideoOrientationEnum


MAX_VIDEO_DURATION_SECONDS = 30 * 60


@dataclass(slots=True)
class VideoMetadata:
    duration_seconds: int
    width: int
    height: int
    bitrate: int | None
    orientation: VideoOrientationEnum
    raw_probe: dict


@dataclass(slots=True)
class VideoQualityPlan:
    variant_type: AssetVariantTypeEnum
    label: str
    width: int
    height: int


@dataclass(slots=True)
class RenderedVideoVariant:
    variant_type: AssetVariantTypeEnum
    label: str
    path: Path
    width: int
    height: int
    bitrate: int | None


class VideoProcessingError(Exception):
    pass


class VideoProcessor:
    async def probe(self, input_path: Path) -> VideoMetadata:
        stdout = await self._run(
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(input_path),
        )
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise VideoProcessingError("ffprobe returned invalid JSON") from exc

        streams = payload.get("streams") or []
        video_stream = next(
            (stream for stream in streams if stream.get("codec_type") == "video"),
            None,
        )
        if video_stream is None:
            raise VideoProcessingError("Uploaded file does not contain a video stream")

        try:
            width = int(video_stream["width"])
            height = int(video_stream["height"])
        except (KeyError, TypeError, ValueError) as exc:
            raise VideoProcessingError("Unable to determine video dimensions") from exc

        duration_raw = video_stream.get("duration") or payload.get("format", {}).get("duration")
        try:
            duration_seconds = int(round(float(duration_raw)))
        except (TypeError, ValueError) as exc:
            raise VideoProcessingError("Unable to determine video duration") from exc

        if duration_seconds <= 0:
            raise VideoProcessingError("Video duration must be positive")
        if duration_seconds > MAX_VIDEO_DURATION_SECONDS:
            raise VideoProcessingError("Video duration exceeds 30 minutes")

        bitrate = None
        bitrate_raw = video_stream.get("bit_rate") or payload.get("format", {}).get("bit_rate")
        if bitrate_raw is not None:
            try:
                bitrate = int(bitrate_raw)
            except (TypeError, ValueError):
                bitrate = None

        return VideoMetadata(
            duration_seconds=duration_seconds,
            width=width,
            height=height,
            bitrate=bitrate,
            orientation=self._orientation(width=width, height=height),
            raw_probe=payload,
        )

    async def transcode_variants(
        self,
        *,
        input_path: Path,
        output_dir: Path,
        metadata: VideoMetadata,
    ) -> list[RenderedVideoVariant]:
        rendered: list[RenderedVideoVariant] = []
        for plan in build_quality_plans(width=metadata.width, height=metadata.height):
            output_path = output_dir / f"{plan.variant_type.value}.mp4"
            await self._run(
                "ffmpeg",
                "-y",
                "-i",
                str(input_path),
                "-vf",
                f"scale={plan.width}:{plan.height}",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-movflags",
                "+faststart",
                str(output_path),
            )
            rendered.append(
                RenderedVideoVariant(
                    variant_type=plan.variant_type,
                    label=plan.label,
                    path=output_path,
                    width=plan.width,
                    height=plan.height,
                    bitrate=None,
                )
            )
        return rendered

    async def _run(self, *args: str) -> str:
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            detail = stderr.decode("utf-8", errors="replace").strip()
            raise VideoProcessingError(detail or f"{args[0]} failed")
        return stdout.decode("utf-8", errors="replace")

    def _orientation(self, *, width: int, height: int) -> VideoOrientationEnum:
        if width == height:
            return VideoOrientationEnum.SQUARE
        return VideoOrientationEnum.LANDSCAPE if width > height else VideoOrientationEnum.PORTRAIT


def build_quality_plans(*, width: int, height: int) -> list[VideoQualityPlan]:
    orientation = VideoOrientationEnum.SQUARE
    if width > height:
        orientation = VideoOrientationEnum.LANDSCAPE
    elif height > width:
        orientation = VideoOrientationEnum.PORTRAIT

    targets = [
        (AssetVariantTypeEnum.VIDEO_1080P, "1080p", 1080),
        (AssetVariantTypeEnum.VIDEO_720P, "720p", 720),
        (AssetVariantTypeEnum.VIDEO_480P, "480p", 480),
        (AssetVariantTypeEnum.VIDEO_360P, "360p", 360),
    ]
    plans: list[VideoQualityPlan] = []
    for variant_type, label, target in targets:
        if orientation == VideoOrientationEnum.LANDSCAPE:
            if height < target:
                continue
            target_height = _even(target)
            target_width = _even_round(width * target_height / height)
        elif orientation == VideoOrientationEnum.PORTRAIT:
            if width < target:
                continue
            target_width = _even(target)
            target_height = _even_round(height * target_width / width)
        else:
            if width < target:
                continue
            target_width = _even(target)
            target_height = _even(target)

        plans.append(
            VideoQualityPlan(
                variant_type=variant_type,
                label=label,
                width=target_width,
                height=target_height,
            )
        )
    return plans


def _even(value: int) -> int:
    return value if value % 2 == 0 else value - 1


def _even_round(value: float) -> int:
    rounded = int(round(value))
    if rounded % 2 == 0:
        return rounded
    floor_even = rounded - 1
    ceil_even = rounded + 1
    return floor_even if abs(value - floor_even) <= abs(value - ceil_even) else ceil_even
