from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.archtool_conf.bundle_project import todo_service, user_service

app = FastAPI(title="Todo App", version="1.0.0")


class UserCreate(BaseModel):
    name: str


class TodoCreate(BaseModel):
    title: str
    user_id: int


@app.post("/users", response_model=dict)
def create_user(payload: UserCreate):
    return user_service.create_user(payload.name)


@app.get("/users", response_model=list[dict])
def get_users():
    return user_service.get_users()


@app.post("/todos", response_model=dict)
def create_todo(payload: TodoCreate):
    try:
        return todo_service.create_todo(payload.title, payload.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc


@app.get("/todos", response_model=list[dict])
def get_todos():
    return todo_service.get_todos()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("entrypoints.run:app", host="127.0.0.1", port=8000, reload=True)