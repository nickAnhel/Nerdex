from __future__ import annotations

import datetime as dt
import os
import uuid
from dataclasses import dataclass, field

from PIL import Image

from src.assets.enums import AssetVariantStatusEnum, AssetVariantTypeEnum
from src.assets.storage import AssetStorage
from src.demo_seed.generators.assets import SeedAssetBuilder
from src.demo_seed.loaders.models import FeaturedUsersEnvelope, TopicsConfig
from src.demo_seed.logging import get_logger
from src.demo_seed.media.covers_generator import generate_initials_avatar
from src.demo_seed.planning.affinity import build_interest_vector, derive_expected_tags
from src.demo_seed.planning.personas import DEFAULT_PERSONAS
from src.demo_seed.planning.plans import PlannedAsset, PlannedAssetVariant, PlannedUser
from src.demo_seed.planning.random_state import SeedRandom
from src.demo_seed.planning.time_distribution import TimeDistributor
from src.demo_seed.media.uploader import upload_bytes_to_s3
from src.users.utils import get_password_hash

logger = get_logger(__name__)


@dataclass(slots=True)
class UsersPlanResult:
    users: list[PlannedUser]
    assets: list[PlannedAsset]


def _translate_presentation_note(note: str, role: str) -> str:
    if note and all(ord(ch) < 128 for ch in note):
        return note
    mapping = {
        "active_author": "Featured active author account for recommendation showcase.",
        "popular_author": "Featured popular author for high-engagement recommendation checks.",
        "active_commenter": "Featured active commenter profile for interaction-heavy scenarios.",
        "regular_user": "Featured regular user profile for feed and subscription behavior checks.",
        "cold_start_user": "Featured near-cold-start profile for recommendation bootstrap testing.",
    }
    return mapping.get(role, "Featured demo profile for recommendation evaluation.")


def _resize_avatar(payload: bytes, size: tuple[int, int]) -> bytes:
    from io import BytesIO

    source = Image.open(BytesIO(payload)).convert("RGBA")
    source = source.resize(size)
    output = BytesIO()
    source.save(output, format="PNG")
    return output.getvalue()


async def build_users(
    *,
    random: SeedRandom,
    distributor: TimeDistributor,
    topics: TopicsConfig,
    featured_users: FeaturedUsersEnvelope,
    storage: AssetStorage,
    seed_run_id: str,
    total_users: int,
) -> UsersPlanResult:
    logger.info("Users: planning %s users (including featured profiles)", total_users)
    users: list[PlannedUser] = []
    assets: list[PlannedAsset] = []
    asset_builder = SeedAssetBuilder(storage=storage, seed_run_id=seed_run_id)

    fallback_password = featured_users.defaults.get("fallback_password", "Demo123456!")
    password = os.getenv(featured_users.defaults.get("password_env", "DEMO_SEED_USER_PASSWORD"), fallback_password)
    hashed_password = get_password_hash(password)

    # Featured users first (exact usernames).
    for item in featured_users.featured_users:
        user_id = uuid.uuid4()
        created_at = distributor.random_user_created_at()
        interests = item.interests or build_interest_vector(random, topics, primary_topic=None)
        expected_tags = item.expected_tags or derive_expected_tags(interests, topics)
        marker = f" [seed_run_id={seed_run_id}]"
        user = PlannedUser(
            user_id=user_id,
            username=item.username,
            display_name=item.display_name,
            hashed_password=hashed_password,
            bio=(item.bio + marker).strip(),
            links=item.links,
            is_admin=bool(featured_users.defaults.get("is_admin", False)),
            created_at=created_at,
            interests=interests,
            preferred_content_types=item.preferred_content_types,
            expected_tags=expected_tags,
            role=item.role,
            is_featured=True,
            presentation_note_en=_translate_presentation_note(item.presentation_note, item.role),
        )
        users.append(user)
    logger.info("Users: prepared %s featured users", len(users))

    topic_slugs = list(topics.topics.keys())
    persona_by_role = {persona.role: persona for persona in DEFAULT_PERSONAS}

    # Generated demo users.
    while len(users) < total_users:
        idx = len(users) + 1
        role = random.choice(list(persona_by_role.keys()))
        primary_topic = random.choice(topic_slugs)
        persona = persona_by_role[role]
        username = f"demo_{primary_topic}_{idx:03d}"
        display_name = f"{persona.display_prefix} {primary_topic.replace('_', ' ').title()} {idx:03d}"
        interests = build_interest_vector(random, topics, primary_topic=primary_topic)
        expected_tags = derive_expected_tags(interests, topics)
        preferred_content_types = {
            "post": round(random.uniform(0.2, 0.4), 3),
            "article": round(random.uniform(0.2, 0.4), 3),
            "video": round(random.uniform(0.1, 0.3), 3),
            "moment": round(random.uniform(0.05, 0.2), 3),
        }
        topic_title = topics.topics[primary_topic].title
        marker = f" [seed_run_id={seed_run_id}]"
        user = PlannedUser(
            user_id=uuid.uuid4(),
            username=username,
            display_name=display_name,
            hashed_password=hashed_password,
            bio=(persona.bio_template.format(topic_title=topic_title) + marker).strip(),
            links=[
                {"label": "Portfolio", "url": f"https://example.com/demo/{username}"},
            ],
            is_admin=False,
            created_at=distributor.random_user_created_at(),
            interests=interests,
            preferred_content_types=preferred_content_types,
            expected_tags=expected_tags,
            role=role,
            is_featured=False,
            presentation_note_en=f"Generated {role.replace('_', ' ')} profile focused on {topic_title.lower()}.",
        )
        users.append(user)
        if len(users) % 10 == 0:
            logger.info("Users: generated %s/%s profiles", len(users), total_users)

    # Generate avatars (initials/abstract only).
    logger.info("Users: generating and uploading avatars")
    for user in users:
        initials = "".join(part[0] for part in user.display_name.split()[:2] if part) or "DU"
        avatar = generate_initials_avatar(initials=initials)
        planned_asset = await asset_builder.from_bytes(
            owner_id=user.user_id,
            payload=avatar.payload,
            filename=f"{user.username}_avatar_original.png",
            mime_type="image/png",
            key_suffix=f"avatars/{user.user_id}",
            usage_target="avatar",
            topic=max(user.interests, key=user.interests.get),
            provider="generated",
            provider_item_id=user.username,
            width=avatar.width,
            height=avatar.height,
            variant_type=AssetVariantTypeEnum.ORIGINAL,
        )

        # Add avatar medium and small variants required by existing user presentation builder.
        medium_payload = _resize_avatar(avatar.payload, (256, 256))
        small_payload = _resize_avatar(avatar.payload, (96, 96))

        medium_key = f"demo/{seed_run_id}/avatars/{user.user_id}/{user.username}_avatar_medium.png"
        small_key = f"demo/{seed_run_id}/avatars/{user.user_id}/{user.username}_avatar_small.png"

        medium_stored = await upload_bytes_to_s3(storage, payload=medium_payload, key=medium_key, mime_type="image/png")
        small_stored = await upload_bytes_to_s3(storage, payload=small_payload, key=small_key, mime_type="image/png")

        planned_asset.variants.append(
            PlannedAssetVariant(
                asset_variant_id=uuid.uuid4(),
                asset_variant_type=AssetVariantTypeEnum.AVATAR_MEDIUM.value,
                storage_bucket=storage.private_bucket,
                storage_key=medium_key,
                mime_type="image/png",
                size_bytes=medium_stored.size_bytes,
                width=256,
                height=256,
                duration_ms=None,
                bitrate=None,
                checksum_sha256=medium_stored.checksum_sha256,
                is_primary=False,
                status=AssetVariantStatusEnum.READY.value,
            )
        )
        planned_asset.variants.append(
            PlannedAssetVariant(
                asset_variant_id=uuid.uuid4(),
                asset_variant_type=AssetVariantTypeEnum.AVATAR_SMALL.value,
                storage_bucket=storage.private_bucket,
                storage_key=small_key,
                mime_type="image/png",
                size_bytes=small_stored.size_bytes,
                width=96,
                height=96,
                duration_ms=None,
                bitrate=None,
                checksum_sha256=small_stored.checksum_sha256,
                is_primary=False,
                status=AssetVariantStatusEnum.READY.value,
            )
        )

        user.avatar_asset_id = planned_asset.asset_id
        assets.append(planned_asset)
        if len(assets) % 10 == 0:
            logger.info("Users: uploaded avatars %s/%s", len(assets), len(users))

    logger.info("Users: completed (%s users, %s avatar assets)", len(users), len(assets))

    return UsersPlanResult(users=users, assets=assets)
