from fastapi import HTTPException, status
from fastapi.requests import Request

from src.articles.exceptions import ArticleNotFound, InvalidArticle


async def article_not_found_handler(request: Request, exc: ArticleNotFound) -> HTTPException:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=str(exc),
    )


async def invalid_article_handler(request: Request, exc: InvalidArticle) -> HTTPException:
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=str(exc),
    )
