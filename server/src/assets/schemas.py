import datetime
import uuid

from pydantic import Field

from src.assets.enums import AssetAccessTypeEnum, AssetStatusEnum, AssetTypeEnum, AssetVariantStatusEnum, AssetVariantTypeEnum
from src.common.schemas import BaseSchema


class AssetInitUploadRequest(BaseSchema):
    filename: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(gt=0)
    declared_mime_type: str | None = Field(default=None, max_length=255)
    asset_type: AssetTypeEnum
    usage_context: str | None = Field(default=None, max_length=128)


class AssetVariantGet(BaseSchema):
    asset_variant_type: AssetVariantTypeEnum
    mime_type: str
    size_bytes: int
    width: int | None = None
    height: int | None = None
    duration_ms: int | None = None
    status: AssetVariantStatusEnum
    url: str | None = None


class AssetGet(BaseSchema):
    asset_id: uuid.UUID
    asset_type: AssetTypeEnum
    status: AssetStatusEnum
    original_filename: str | None = None
    size_bytes: int | None = None
    access_type: AssetAccessTypeEnum
    variants: list[AssetVariantGet]
    created_at: datetime.datetime
    updated_at: datetime.datetime


class AssetInitUploadResponse(BaseSchema):
    asset: AssetGet
    upload_url: str
    upload_method: str = "PUT"
    upload_headers: dict[str, str] = Field(default_factory=dict)
    expires_in_seconds: int


class AssetFinalizeUploadResponse(BaseSchema):
    asset: AssetGet
