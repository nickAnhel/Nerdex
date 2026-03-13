from fastapi import HTTPException, status
from fastapi.requests import Request

from src.assets.exceptions import AssetNotFound, AssetUploadNotReady, InvalidAsset


async def asset_not_found_handler(request: Request, exc: AssetNotFound) -> HTTPException:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=str(exc),
    )


async def invalid_asset_handler(request: Request, exc: InvalidAsset) -> HTTPException:
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=str(exc),
    )


async def asset_upload_not_ready_handler(
    request: Request,
    exc: AssetUploadNotReady,
) -> HTTPException:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=str(exc),
    )
