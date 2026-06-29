from fastapi import APIRouter
from sqlalchemy.ext.asyncio import async_sessionmaker
from web_fractal.db import UnitOfWork

from app.todos.dtos import CreateTodoDTO
from app.todos.interfaces import TodoControllerABC, TodoServiceABC


class TodoController(TodoControllerABC):
    router: APIRouter = APIRouter(prefix="/todos", tags=["todos"])
    service: TodoServiceABC
    session_maker: async_sessionmaker

    __annotations__ = {
        "service": TodoServiceABC,
        "session_maker": async_sessionmaker,
    }

    def init_http_routes(self) -> None:
        self.reg_route(self.create_todo, path="/", response_model=dict, methods=["POST"])
        self.reg_route(self.get_todos, path="/", response_model=list[dict], methods=["GET"])

    async def create_todo(self, dto: CreateTodoDTO) -> dict:
        async with UnitOfWork(self.session_maker) as uow:
            session = uow.get_session()
            try:
                result = await self.service.create_todo(session, dto)
                await session.commit()
                return result
            except ValueError:
                await session.rollback()
                raise

    async def get_todos(self) -> list[dict]:
        async with UnitOfWork(self.session_maker) as uow:
            session = uow.get_session()
            result = await self.service.get_todos(session)
            await session.commit()
            return result
