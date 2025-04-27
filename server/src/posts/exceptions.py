class PostNotFound(Exception):
    """Post not found exception."""

    def __init__(self, message="Post not found"):
        super().__init__(message)


class PostAlreadyRated(Exception):
    """Post already liked or disliked exception."""

    def __init__(self, message="Post already rated"):
        super().__init__(message)
