from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from web_fractal.db import UnitOfWork

from app.users.dtos import CreateUserDTO
from app.users.interfaces import UserControllerABC, UserServiceABC


class UserController(UserControllerABC):
    router: APIRouter = APIRouter(prefix="/users", tags=["users"])
    service: UserServiceABC
    session_maker: async_sessionmaker

    __annotations__ = {
        "service": UserServiceABC,
        "session_maker": async_sessionmaker,
    }

    def init_http_routes(self) -> None:
        self.reg_route(self.create_user, path="/", response_model=dict, methods=["POST"])
        self.reg_route(self.get_users, path="/", response_model=list[dict], methods=["GET"])

    async def create_user(self, dto: CreateUserDTO) -> dict:
        async with UnitOfWork(self.session_maker) as uow:
            session = uow.get_session()
            result = await self.service.create_user(session, dto)
            await session.commit()
            return result

    async def get_users(self) -> list[dict]:
        async with UnitOfWork(self.session_maker) as uow:
            session = uow.get_session()
            result = await self.service.get_users(session)
            await session.commit()
            return result
