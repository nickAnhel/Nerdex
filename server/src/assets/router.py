from uuid import UUID

from fastapi import APIRouter, Depends

from src.assets.dependencies import get_asset_service
from src.assets.schemas import AssetFinalizeUploadResponse, AssetGet, AssetInitUploadRequest, AssetInitUploadResponse
from src.assets.service import AssetService
from src.auth.dependencies import get_current_user
from src.users.schemas import UserGet

router = APIRouter(
    prefix="/assets",
    tags=["Assets"],
)


@router.post("/uploads/init")
async def init_asset_upload(
    data: AssetInitUploadRequest,
    user: UserGet = Depends(get_current_user),
    asset_service: AssetService = Depends(get_asset_service),
) -> AssetInitUploadResponse:
    return await asset_service.init_upload(owner_id=user.user_id, data=data)


@router.post("/uploads/{asset_id}/finalize")
async def finalize_asset_upload(
    asset_id: UUID,
    user: UserGet = Depends(get_current_user),
    asset_service: AssetService = Depends(get_asset_service),
) -> AssetFinalizeUploadResponse:
    return await asset_service.finalize_upload(owner_id=user.user_id, asset_id=asset_id)


@router.get("/{asset_id}")
async def get_asset(
    asset_id: UUID,
    user: UserGet = Depends(get_current_user),
    asset_service: AssetService = Depends(get_asset_service),
) -> AssetGet:
    return await asset_service.get_asset(asset_id=asset_id, owner_id=user.user_id)
