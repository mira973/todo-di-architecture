from uuid import UUID

from pydantic import BaseModel


class UserDM(BaseModel):
    id: UUID
    email: str
    name: str
