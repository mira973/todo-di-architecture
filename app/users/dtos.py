from pydantic import BaseModel


class CreateUserDTO(BaseModel):
    name: str
