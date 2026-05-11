from src.assets.enums import AssetVariantTypeEnum
import json
from pathlib import Path

import pytest

from src.assets.video_processing import VideoProcessingError, VideoProcessor, build_quality_plans
from src.videos.enums import VideoOrientationEnum


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_landscape_quality_plans_use_target_height_and_even_dimensions() -> None:
    plans = build_quality_plans(width=1920, height=1080)

    assert [(plan.variant_type, plan.width, plan.height) for plan in plans] == [
        (AssetVariantTypeEnum.VIDEO_1080P, 1920, 1080),
        (AssetVariantTypeEnum.VIDEO_720P, 1280, 720),
        (AssetVariantTypeEnum.VIDEO_480P, 854, 480),
        (AssetVariantTypeEnum.VIDEO_360P, 640, 360),
    ]


def test_portrait_quality_plans_use_short_side_and_even_dimensions() -> None:
    plans = build_quality_plans(width=1080, height=1920)

    assert [(plan.variant_type, plan.width, plan.height) for plan in plans] == [
        (AssetVariantTypeEnum.VIDEO_1080P, 1080, 1920),
        (AssetVariantTypeEnum.VIDEO_720P, 720, 1280),
        (AssetVariantTypeEnum.VIDEO_480P, 480, 854),
        (AssetVariantTypeEnum.VIDEO_360P, 360, 640),
    ]


def test_quality_plans_do_not_upscale_source() -> None:
    plans = build_quality_plans(width=1280, height=720)

    assert [plan.variant_type for plan in plans] == [
        AssetVariantTypeEnum.VIDEO_720P,
        AssetVariantTypeEnum.VIDEO_480P,
        AssetVariantTypeEnum.VIDEO_360P,
    ]


@pytest.mark.anyio
async def test_probe_extracts_portrait_metadata(monkeypatch) -> None:
    processor = VideoProcessor()

    async def fake_run(*args):  # type: ignore[no-untyped-def]
        return json.dumps({
            "streams": [{
                "codec_type": "video",
                "width": 720,
                "height": 1280,
                "duration": "42.2",
                "bit_rate": "1000",
            }],
            "format": {},
        })

    monkeypatch.setattr(processor, "_run", fake_run)

    metadata = await processor.probe(Path("video.mp4"))

    assert metadata.duration_seconds == 42
    assert metadata.orientation == VideoOrientationEnum.PORTRAIT


@pytest.mark.anyio
async def test_probe_rejects_invalid_json(monkeypatch) -> None:
    processor = VideoProcessor()

    async def fake_run(*args):  # type: ignore[no-untyped-def]
        return "not-json"

    monkeypatch.setattr(processor, "_run", fake_run)

    with pytest.raises(VideoProcessingError, match="invalid JSON"):
        await processor.probe(Path("broken.mp4"))


@pytest.mark.anyio
async def test_probe_rejects_too_long_video(monkeypatch) -> None:
    processor = VideoProcessor()

    async def fake_run(*args):  # type: ignore[no-untyped-def]
        return json.dumps({
            "streams": [{
                "codec_type": "video",
                "width": 1920,
                "height": 1080,
                "duration": str(31 * 60),
            }],
            "format": {},
        })

    monkeypatch.setattr(processor, "_run", fake_run)

    with pytest.raises(VideoProcessingError, match="exceeds 30 minutes"):
        await processor.probe(Path("too-long.mp4"))
