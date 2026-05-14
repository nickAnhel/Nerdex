class UserNotFound(Exception):
    """User not found exception."""

    def __init__(self, message="User not found") -> None:
        super().__init__(message)


class UsernameAlreadyExists(Exception):
    """Username already exists exception."""

    def __init__(self, message="Username already exists") -> None:
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


class InvalidCurrentPassword(Exception):
    """Current password is invalid."""

    def __init__(self, message="Current password is invalid") -> None:
        super().__init__(message)


class WeakPassword(Exception):
    """Password does not meet requirements."""

    def __init__(self, message="Password does not meet requirements") -> None:
        super().__init__(message)


class SamePassword(Exception):
    """New password equals old password."""

    def __init__(self, message="New password must differ from current password") -> None:
        super().__init__(message)
