import uuid

from sqlalchemy.exc import NoResultFound, IntegrityError

from src.users.schemas import UserGet
from src.posts.enums import PostOrder
from src.posts.exceptions import PostNotFound, PostAlreadyRated
from src.posts.repository import PostRepository
from src.posts.schemas import PostCreate, PostGet, PostUpdate, PostRating


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
        """Delete post by id."""

        await self._repository.delete(post_id=post_id, user_id=user.user_id)

    async def get_post_statistics(
        self,
        post_id: uuid.UUID,
    ) -> PostRating:
        likes, dislikes = await self._repository.get_post_rating(post_id=post_id)
        return PostRating(
            post_id=post_id,
            likes=likes,
            dislikes=dislikes,
        )

    async def add_like_to_post(
        self,
        post_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> PostRating:
        """Add like to post."""
        try:
            await self._repository.like(post_id=post_id, user_id=user_id)
        except IntegrityError as exc:
            raise PostAlreadyRated(f"Post with id {post_id!s} already liked by user with id {user_id!s}") from exc

        return await self.get_post_statistics(post_id=post_id)

    async def remove_like_from_post(
        self,
        post_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> PostRating:
        """Remove like from post."""

        await self._repository.unlike(post_id=post_id, user_id=user_id)
        return await self.get_post_statistics(post_id=post_id)

    async def add_dislike_to_post(
        self,
        post_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> PostRating:
        """Add dislike to post."""

        try:
            await self._repository.dislike(post_id=post_id, user_id=user_id)
        except IntegrityError as exc:
            raise PostAlreadyRated(f"Post with id {post_id!s} already disliked by user with id {user_id!s}") from exc

        return await self.get_post_statistics(post_id=post_id)

    async def remove_dislike_from_post(
        self,
        post_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> PostRating:
        """Remove dislike from post."""

        await self._repository.undislike(post_id=post_id, user_id=user_id)
        return await self.get_post_statistics(post_id=post_id)
