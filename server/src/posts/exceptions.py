class PostNotFound(Exception):
    """Post not found or unavailable exception."""

    def __init__(self, message="Post not found"):
        super().__init__(message)


class InvalidPost(Exception):
    """Post payload violates domain rules."""

    def __init__(self, message="Invalid post payload"):
        super().__init__(message)
