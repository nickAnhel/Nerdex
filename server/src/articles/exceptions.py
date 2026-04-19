class ArticleNotFound(Exception):
    """Article not found or unavailable."""

    def __init__(self, message: str = "Article not found") -> None:
        super().__init__(message)


class InvalidArticle(Exception):
    """Article payload violates domain rules."""

    def __init__(self, message: str = "Invalid article payload") -> None:
        super().__init__(message)
