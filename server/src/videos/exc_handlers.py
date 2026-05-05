from fastapi import HTTPException, Request, status

from src.videos.exceptions import InvalidVideo, VideoNotFound


async def video_not_found_handler(request: Request, exc: VideoNotFound) -> HTTPException:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=exc.message,
    )


async def invalid_video_handler(request: Request, exc: InvalidVideo) -> HTTPException:
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=exc.message,
    )
