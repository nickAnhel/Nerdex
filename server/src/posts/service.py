import uuid

from sqlalchemy.exc import NoResultFound

from src.users.schemas import UserGet
from src.posts.enums import PostOrder
from src.posts.exceptions import PostNotFound
from src.posts.repository import PostRepository
from src.posts.schemas import PostCreate, PostGet, PostUpdate


class PostService:
    def __init__(self, repository: PostRepository) -> None:
        self._repository = repository

    async def create_post(
        self,
        user: UserGet,
        data: PostCreate,
    ) -> PostGet:
        """Create new post."""

        post_data = data.model_dump()
        post_data["user_id"] = user.user_id

        post = await self._repository.create(post_data)

        return PostGet.model_validate(post)

    async def get_post(
        self,
        post_id: uuid.UUID,
    ) -> PostGet:
        """Get single post by id."""

        try:
            post = await self._repository.get_single(post_id=post_id)
            return PostGet.model_validate(post)

        except NoResultFound as exc:
            raise PostNotFound(f"Post with id {post_id!s} not found") from exc

    async def get_posts(
        self,
        order: PostOrder,
        desc: bool,
        offset: int,
        limit: int,
    ) -> list[PostGet]:
        """Get posts with pagination and sorting."""

        posts = await self._repository.get_multi(
            order=order,
            order_desc=desc,
            offset=offset,
            limit=limit,
        )

        return [PostGet.model_validate(user) for user in posts]

    async def update_post(
        self,
        user: UserGet,
        post_id: uuid.UUID,
        data: PostUpdate,
    ) -> PostGet:
        """Update post."""

        post = await self._repository.update(
            data=data.model_dump(),
            post_id=post_id,
            user_id=user.user_id,
        )
        return PostGet.model_validate(post)

    async def delete_post(
        self,
        user: UserGet,
        post_id: uuid.UUID,
    ) -> None:
        """Post user by id."""

        await self._repository.delete(post_id=post_id, user_id=user.user_id)
