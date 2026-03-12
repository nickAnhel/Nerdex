class CommentNotFound(Exception):
    """Comment or comment thread not found."""

    def __init__(self, message: str = "Comment not found") -> None:
        super().__init__(message)


class InvalidComment(Exception):
    """Comment payload or state is invalid."""

    def __init__(self, message: str = "Invalid comment") -> None:
        super().__init__(message)
