class PostNotFound(Exception):
    """Post not found or unavailable exception."""

    def __init__(self, message="Post not found"):
        super().__init__(message)
