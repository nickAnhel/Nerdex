from __future__ import annotations

from src.demo_seed.generators.assets import ManifestItem


def build_manifest_report(items: list[ManifestItem]) -> dict:
    return {
        "assets": [
            {
                "seed_run_id": item.seed_run_id,
                "usage_target": item.usage_target,
                "topic": item.topic,
                "provider": item.provider,
                "provider_item_id": item.provider_item_id,
                "media_type": item.media_type,
                "local_path": item.local_path,
                "s3_key": item.s3_key,
                "metadata": item.metadata,
            }
            for item in items
        ]
    }
