class UserNotFound(Exception):
    """User not found exception."""

    def __init__(self, message="User not found"):
        super().__init__(message)


class UsernameOrEmailAlreadyExists(Exception):
    """Username or email already exists exception."""

    def __init__(self, message="Username or email already exists"):
        super().__init__(message)
