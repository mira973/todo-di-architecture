from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.todos.dtos import CreateTodoDTO
from app.todos.interfaces import TodoRepoABC, TodoServiceABC
from app.users.interfaces import UserServiceABC


class TodoService(TodoServiceABC):
    repo: TodoRepoABC
    user_service: UserServiceABC

    __annotations__ = {
        "repo": TodoRepoABC,
        "user_service": UserServiceABC,
    }

    async def create_todo(self, session: AsyncSession, dto: CreateTodoDTO) -> dict:
        if not await self.user_service.user_exists(session, dto.user_id):
            raise ValueError("User not found")
        return await self.repo.create(session, dto)

    async def get_todos(self, session: AsyncSession) -> list[dict]:
        return await self.repo.list(session)
