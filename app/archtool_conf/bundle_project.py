from pathlib import Path

from archtool.dependency_injector import DependencyInjector
from archtool.global_types import AppModule
from archtool.layers.default_layers import DomainLayer, InfrastructureLayer

from app.todos.interfaces import TodoControllerABC, TodoRepoABC, TodoServiceABC
from app.todos.repos import TodoRepo
from app.todos.services import TodoService
from app.users.interfaces import UserControllerABC, UserRepoABC, UserServiceABC
from app.users.repos import UserRepo
from app.users.services import UserService
from app.users.controllers import UserController
from app.todos.controllers import TodoController

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

user_controller = UserController()
todo_controller = TodoController()
user_controller.service = user_service
todo_controller.service = todo_service

__all__ = ["user_controller", "todo_controller"]
