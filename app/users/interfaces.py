from abc import ABC, abstractmethod

from archtool.layers.default_layer_interfaces import ABCRepo, ABCService
from sqlalchemy.ext.asyncio import AsyncSession
from web_fractal.http.interfaces import HttpControllerABC

try:
    from archtool.layers.default_layer_interfaces import ABCController
except ImportError:  # pragma: no cover
    ABCController = ABC

from .dtos import CreateUserDTO


class UserRepoABC(ABCRepo):
    @abstractmethod
    async def create(self, session: AsyncSession, dto: CreateUserDTO) -> dict:
        ...

    @abstractmethod
    async def list(self, session: AsyncSession) -> list[dict]:
        ...

    @abstractmethod
    async def exists(self, session: AsyncSession, user_id: int | str) -> bool:
        ...


class UserServiceABC(ABCService):
    @abstractmethod
    async def create_user(self, session: AsyncSession, dto: CreateUserDTO) -> dict:
        ...

    @abstractmethod
    async def get_users(self, session: AsyncSession) -> list[dict]:
        ...

    @abstractmethod
    async def user_exists(self, session: AsyncSession, user_id: int | str) -> bool:
        ...


class UserControllerABC(ABCController, HttpControllerABC):
    @abstractmethod
    async def create_user(self, dto: CreateUserDTO) -> dict:
        ...

    @abstractmethod
    async def get_users(self) -> list[dict]:
        ...
