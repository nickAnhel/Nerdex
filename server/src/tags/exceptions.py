class InvalidTag(Exception):
    """Raised when a tag or tag prefix does not satisfy validation rules."""

    def __init__(self, message: str = "Invalid tag") -> None:
        super().__init__(message)
