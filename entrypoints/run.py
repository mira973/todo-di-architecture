from fastapi import FastAPI, HTTPException

from app.archtool_conf.bundle_project import todo_controller, user_controller
from app.todos.dtos import CreateTodoDTO
from app.users.dtos import CreateUserDTO

app = FastAPI(title="Todo App", version="1.0.0")


@app.post("/users", response_model=dict)
def create_user(payload: CreateUserDTO):
    return user_controller.create_user(payload)


@app.get("/users", response_model=list[dict])
def get_users():
    return user_controller.get_users()


@app.post("/todos", response_model=dict)
def create_todo(payload: CreateTodoDTO):
    try:
        return todo_controller.create_todo(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc


@app.get("/todos", response_model=list[dict])
def get_todos():
    return todo_controller.get_todos()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("entrypoints.run:app", host="127.0.0.1", port=8000, reload=True)