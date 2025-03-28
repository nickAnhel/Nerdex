from enum import Enum


class UserOrder(str, Enum):
    ID = "user_id"

    def __str__(self) -> str:
        return self.value
