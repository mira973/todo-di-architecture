from abc import ABC, abstractmethod

from archtool.layers.default_layer_interfaces import ABCRepo, ABCService
from sqlalchemy.ext.asyncio import AsyncSession
from web_fractal.http.interfaces import HttpControllerABC

try:
    from archtool.layers.default_layer_interfaces import ABCController
except ImportError:  # pragma: no cover
    ABCController = ABC

from .dtos import CreateTodoDTO


class TodoRepoABC(ABCRepo):
    @abstractmethod
    async def create(self, session: AsyncSession, dto: CreateTodoDTO) -> dict:
        ...

    @abstractmethod
    async def list(self, session: AsyncSession) -> list[dict]:
        ...


class TodoServiceABC(ABCService):
    @abstractmethod
    async def create_todo(self, session: AsyncSession, dto: CreateTodoDTO) -> dict:
        ...

    @abstractmethod
    async def get_todos(self, session: AsyncSession) -> list[dict]:
        ...


class TodoControllerABC(ABCController, HttpControllerABC):
    @abstractmethod
    async def create_todo(self, dto: CreateTodoDTO) -> dict:
        ...

    @abstractmethod
    async def get_todos(self) -> list[dict]:
        ...
