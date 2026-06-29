from abc import abstractmethod

from archtool.layers.default_layer_interfaces import ABCRepo, ABCService


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
