from app.users.dtos import CreateUserDTO
from app.users.interfaces import UserControllerABC, UserServiceABC


class UserController(UserControllerABC):
    service: UserServiceABC

    def create_user(self, dto: CreateUserDTO) -> dict:
        return self.service.create_user(dto.name)

    def get_users(self) -> list[dict]:
        return self.service.get_users()
