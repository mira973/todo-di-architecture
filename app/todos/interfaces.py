from abc import abstractmethod
from abc import ABC

from archtool.layers.default_layer_interfaces import ABCRepo, ABCService

try:
    from archtool.layers.default_layer_interfaces import ABCController
except ImportError:  # pragma: no cover
    ABCController = ABC

from .dtos import CreateTodoDTO


class TodoRepoABC(ABCRepo):
    @abstractmethod
    def add(self, title: str, user_id: int) -> dict:
        ...

    @abstractmethod
    def get_all(self) -> list[dict]:
        ...


class TodoServiceABC(ABCService):
    @abstractmethod
    def create_todo(self, title: str, user_id: int) -> dict:
        ...

    @abstractmethod
    def get_todos(self) -> list[dict]:
        ...


class TodoControllerABC(ABCController):
    @abstractmethod
    def create_todo(self, dto: CreateTodoDTO) -> dict:
        ...

    @abstractmethod
    def get_todos(self) -> list[dict]:
        ...
