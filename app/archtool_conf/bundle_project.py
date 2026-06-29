from pathlib import Path

from archtool.dependency_injector import DependencyInjector
from archtool.global_types import AppModule
from archtool.layers.default_layers import DomainLayer, InfrastructureLayer

from app.todos.interfaces import TodoRepoABC, TodoServiceABC
from app.todos.repos import TodoRepo
from app.todos.services import TodoService
from app.users.interfaces import UserRepoABC, UserServiceABC
from app.users.repos import UserRepo
from app.users.services import UserService

PROJECT_ROOT = Path(__file__).resolve().parents[2]

injector = DependencyInjector(
    modules_list=[AppModule("app.users"), AppModule("app.todos")],
    layers=[InfrastructureLayer, DomainLayer],
    project_root=PROJECT_ROOT,
)

user_repo = UserRepo()
todo_repo = TodoRepo()

injector.register(key=UserRepoABC, value=user_repo, inject_into=False)
injector.register(key=TodoRepoABC, value=todo_repo, inject_into=False)
injector.inject()

user_service = UserService()
todo_service = TodoService()
user_service.repo = user_repo
todo_service.repo = todo_repo
todo_service.user_service = user_service

__all__ = ["user_service", "todo_service"]

__all__ = ["user_service", "todo_service"]
