class MomentNotFound(Exception):
    def __init__(self, message: str = "Moment not found") -> None:
        self.message = message


class InvalidMoment(Exception):
    def __init__(self, message: str = "Invalid moment") -> None:
        self.message = message
