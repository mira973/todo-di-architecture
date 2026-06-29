from abc import abstractmethod
from abc import ABC

from archtool.layers.default_layer_interfaces import ABCRepo, ABCService

try:
    from archtool.layers.default_layer_interfaces import ABCController
except ImportError:  # pragma: no cover
    ABCController = ABC

from .dtos import CreateUserDTO


class UserRepoABC(ABCRepo):
    @abstractmethod
    def add(self, name: str) -> dict:
        ...

    @abstractmethod
    def get_all(self) -> list[dict]:
        ...

    @abstractmethod
    def exists(self, user_id: int) -> bool:
        ...


class UserServiceABC(ABCService):
    @abstractmethod
    def create_user(self, name: str) -> dict:
        ...

    @abstractmethod
    def get_users(self) -> list[dict]:
        ...

    @abstractmethod
    def user_exists(self, user_id: int) -> bool:
        ...


class UserControllerABC(ABCController):
    @abstractmethod
    def create_user(self, dto: CreateUserDTO) -> dict:
        ...

    @abstractmethod
    def get_users(self) -> list[dict]:
        ...
