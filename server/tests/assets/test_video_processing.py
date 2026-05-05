from src.assets.enums import AssetVariantTypeEnum
from src.assets.video_processing import build_quality_plans


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
