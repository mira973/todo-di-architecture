from fastapi import FastAPI
from arch_demo import user_service, todo_service

app = FastAPI()

@app.post("/users")
def create_user(name: str):
    return user_service.create_user(name)

@app.get("/users")
def get_users():
    return user_service.get_users()

@app.post("/todos")
def create_todo(title: str, user_id: int):
    return todo_service.create_todo(title, user_id)

@app.get("/todos")
def get_todos():
    return todo_service.get_todos()