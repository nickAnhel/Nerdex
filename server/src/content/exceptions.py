class ContentNotFound(Exception):
    def __init__(self, message: str = "Content not found") -> None:
        self.message = message
        super().__init__(message)


class InvalidContentAction(Exception):
    def __init__(self, message: str = "Invalid content action") -> None:
        self.message = message
        super().__init__(message)
