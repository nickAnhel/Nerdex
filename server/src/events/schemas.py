import datetime
import uuid

from src.events.enums import EventType
from src.schemas import BaseSchema
from src.users.schemas import UserGet


class EventCreate(BaseSchema):
    chat_id: uuid.UUID
    user_id: uuid.UUID
    event_type: EventType
    altered_user_id: uuid.UUID | None = None


class EventGet(EventCreate):
    event_id: uuid.UUID
    created_at: datetime.datetime


class EventGetWithUsers(EventGet):
    user: UserGet
    altered_user: UserGet | None
