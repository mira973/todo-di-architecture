from app.todos.dtos import CreateTodoDTO
from app.todos.interfaces import TodoControllerABC, TodoServiceABC


class TodoController(TodoControllerABC):
    service: TodoServiceABC

    def create_todo(self, dto: CreateTodoDTO) -> dict:
        return self.service.create_todo(dto.title, dto.user_id)

    def get_todos(self) -> list[dict]:
        return self.service.get_todos()
