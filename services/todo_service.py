from fastapi import HTTPException

class TodoService:
    def __init__(self, todo_repo, user_repo):
        self.todo_repo = todo_repo
        self.user_repo = user_repo

    def create_todo(self, title: str, user_id: int):
        if not self.user_repo.exists(user_id):
            raise HTTPException(status_code=404, detail="User not found")
        return self.todo_repo.add(title, user_id)

    def get_todos(self):
        return self.todo_repo.get_all()