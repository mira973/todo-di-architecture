from app.todos.interfaces import TodoRepoABC, TodoServiceABC
from app.users.interfaces import UserServiceABC


class TodoService(TodoServiceABC):
    repo: TodoRepoABC
    user_service: UserServiceABC

    def create_todo(self, title: str, user_id: int) -> dict:
        if not self.user_service.user_exists(user_id):
            raise ValueError("User not found")
        return self.repo.add(title, user_id)

    def get_todos(self) -> list[dict]:
        return self.repo.get_all()
