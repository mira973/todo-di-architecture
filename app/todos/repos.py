from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.todos.dtos import CreateTodoDTO
from app.todos.interfaces import TodoRepoABC
from app.todos.models import Todo


class TodoRepo(TodoRepoABC):
    pass
    async def create(self, session: AsyncSession, dto: CreateTodoDTO) -> dict:
        todo = Todo(title=dto.title, user_id=str(dto.user_id), completed=False)
        session.add(todo)
        await session.flush()
        await session.refresh(todo)

        return {"id": str(todo.id), "title": todo.title, "user_id": str(todo.user_id), "completed": todo.completed}

    async def list(self, session: AsyncSession) -> list[dict]:
        result = await session.execute(select(Todo))
        todos = result.scalars().all()
        return [{"id": str(todo.id), "title": todo.title, "user_id": str(todo.user_id), "completed": todo.completed} for todo in todos]
