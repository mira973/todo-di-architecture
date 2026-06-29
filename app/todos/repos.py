from app.todos.interfaces import TodoRepoABC


class TodoRepo(TodoRepoABC):
    def __init__(self):
        self.todos = []
        self.counter = 1

    def add(self, title: str, user_id: int) -> dict:
        todo = {"id": self.counter, "title": title, "user_id": user_id}
        self.todos.append(todo)
        self.counter += 1
        return todo

    def get_all(self) -> list[dict]:
        return self.todos
