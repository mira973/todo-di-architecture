from repositories.user_repo import UserRepo
from repositories.todo_repo import TodoRepo
from services.user_service import UserService
from services.todo_service import TodoService

user_repo = UserRepo()
todo_repo = TodoRepo()

user_service = UserService(user_repo)
todo_service = TodoService(todo_repo, user_repo)