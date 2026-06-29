from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.users.dtos import CreateUserDTO
from app.users.interfaces import UserRepoABC
from app.users.models import User


class UserRepo(UserRepoABC):
    pass
    async def create(self, session: AsyncSession, dto: CreateUserDTO) -> dict:
        user = User(email=dto.email, name=dto.name)
        session.add(user)
        await session.flush()
        await session.refresh(user)

        return {"id": str(user.id), "email": user.email, "name": user.name}

    async def list(self, session: AsyncSession) -> list[dict]:
        result = await session.execute(select(User))
        users = result.scalars().all()
        return [{"id": str(user.id), "email": user.email, "name": user.name} for user in users]

    async def exists(self, session: AsyncSession, user_id: int | UUID | str) -> bool:
        result = await session.execute(select(User).where(User.id == str(user_id)))
        return result.scalar_one_or_none() is not None
