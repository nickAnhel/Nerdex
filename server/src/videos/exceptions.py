class VideoNotFound(Exception):
    def __init__(self, message: str = "Video not found") -> None:
        self.message = message


class InvalidVideo(Exception):
    def __init__(self, message: str = "Invalid video") -> None:
        self.message = message
