from __future__ import annotations

from pathlib import Path

from src.demo_seed.loaders._yaml import load_yaml
from src.demo_seed.loaders.models import FeaturedUserConfig, FeaturedUsersEnvelope


def load_featured_users(path: Path) -> FeaturedUsersEnvelope:
    data = load_yaml(path)
    raw_items = data.get("featured_users") or []
    users = [
        FeaturedUserConfig(
            username=item["username"],
            display_name=item.get("display_name", item["username"]),
            role=item.get("role", "regular_user"),
            bio=item.get("bio", ""),
            links=list(item.get("links") or []),
            interests={k: float(v) for k, v in (item.get("interests") or {}).items()},
            preferred_content_types={k: float(v) for k, v in (item.get("preferred_content_types") or {}).items()},
            expected_tags=list(item.get("expected_tags") or []),
            author_profile=dict(item.get("author_profile") or {}),
            presentation_note=item.get("presentation_note", ""),
        )
        for item in raw_items
    ]
    return FeaturedUsersEnvelope(
        version=int(data.get("version", 1)),
        defaults=dict(data.get("defaults") or {}),
        featured_users=users,
    )
