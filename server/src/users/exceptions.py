class UserNotFound(Exception):
    """User not found exception."""

    def __init__(self, message="User not found") -> None:
        super().__init__(message)


class UsernameOrEmailAlreadyExists(Exception):
    """Username or email already exists exception."""

    def __init__(self, message="Username or email already exists") -> None:
        super().__init__(message)


class CantSubscribeToUser(Exception):
    """Can't subscribe to user exception."""

    def __init__(self, message="Can't subscribe to user") -> None:
        super().__init__(message)


class CantUnsubscribeFromUser(Exception):
    """Can't unsubscribe from user exception."""

    def __init__(self, message="Can't unsubscribe from user") -> None:
        super().__init__(message)


class UserNotInSubscriptions(Exception):
    """User not in subscriptions exception."""

    def __init__(self, message="User not in subscriptions") -> None:
        super().__init__(message)
