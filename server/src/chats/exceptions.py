class ChatNotFound(Exception):
    """Raised when chat is not found"""


class AlreadyInChat(Exception):
    """Raised when user is already in chat"""


class FailedToLeaveChat(Exception):
    """Raised when failed to leave chat"""


class CantAddMembers(Exception):
    """Raised when cannot add members to chat"""


class CantRemoveMembers(Exception):
    """Raised when cannot remove members from chat"""
