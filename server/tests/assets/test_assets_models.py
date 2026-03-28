import uuid

import src.chats.models  # noqa: F401
import src.comments.models  # noqa: F401
import src.content.models  # noqa: F401
import src.events.models  # noqa: F401
import src.messages.models  # noqa: F401
import src.posts.models  # noqa: F401

from src.assets.models import AssetModel, AssetVariantModel, ContentAssetModel, MessageAssetModel
from src.users.models import UserModel


def test_content_asset_model_uses_composite_primary_key() -> None:
    primary_key_columns = {column.name for column in ContentAssetModel.__table__.primary_key.columns}

    assert primary_key_columns == {"content_id", "asset_id", "content_asset_type"}


def test_message_asset_model_uses_composite_primary_key() -> None:
    primary_key_columns = {column.name for column in MessageAssetModel.__table__.primary_key.columns}

    assert primary_key_columns == {"message_id", "asset_id"}


def test_asset_variant_model_has_expected_unique_constraints() -> None:
    constraints = {
        tuple(column.name for column in constraint.columns)
        for constraint in AssetVariantModel.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }

    assert ("asset_id", "asset_variant_type") in constraints
    assert ("storage_bucket", "storage_key") in constraints


def test_user_model_has_avatar_asset_column_and_relationship() -> None:
    assert "avatar_asset_id" in UserModel.__table__.c
    assert "avatar_crop" in UserModel.__table__.c
    assert UserModel.avatar_asset.property.mapper.class_ is AssetModel


def test_asset_model_relationships_include_content_and_message_links() -> None:
    assert AssetModel.content_links.property.mapper.class_ is ContentAssetModel
    assert AssetModel.message_links.property.mapper.class_ is MessageAssetModel


def test_user_avatar_asset_id_accepts_uuid_values() -> None:
    avatar_asset_id = uuid.uuid4()
    user = UserModel(
        user_id=uuid.uuid4(),
        username="tester",
        hashed_password="hashed",
        avatar_asset_id=avatar_asset_id,
    )

    assert user.avatar_asset_id == avatar_asset_id
