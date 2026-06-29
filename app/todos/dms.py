from uuid import UUID

from pydantic import BaseModel


class TodoDM(BaseModel):
    id: UUID
    title: str
    user_id: UUID
    completed: bool
