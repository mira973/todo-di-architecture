from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.users.dtos import CreateUserDTO
from app.users.interfaces import UserRepoABC, UserServiceABC


class UserService(UserServiceABC):
    repo: UserRepoABC

    __annotations__ = {"repo": UserRepoABC}

    async def create_user(self, session: AsyncSession, dto: CreateUserDTO) -> dict:
        return await self.repo.create(session, dto)

    async def get_users(self, session: AsyncSession) -> list[dict]:
        return await self.repo.list(session)

    async def user_exists(self, session: AsyncSession, user_id: int | UUID | str) -> bool:
        return await self.repo.exists(session, user_id)
