# 📝 ToDo App: FastAPI + archtool DI

Минимальный учебный backend-проект на FastAPI, который демонстрирует archtool-based dependency injection без SQLAlchemy, web_fractal и async-слоя.

## Что здесь есть

- FastAPI endpoints
- archtool DependencyInjector
- AppModule-based module discovery
- repository/service layers
- in-memory storage
- DI through class annotations

## Структура проекта

```text
todo_app/
├── app/
│   ├── archtool_conf/
│   │   └── bundle_project.py
│   ├── users/
│   │   ├── interfaces.py
│   │   ├── repos.py
│   │   └── services.py
│   └── todos/
│       ├── interfaces.py
│       ├── repos.py
│       └── services.py
└── entrypoints/
    └── run.py
```

## Запуск

```bash
pip install archtool fastapi uvicorn
python -m entrypoints.run
```

Swagger UI будет доступен по адресу:

```text
http://127.0.0.1:8000/docs
```

## Endpoints

- POST /users
- GET /users
- POST /todos
- GET /todos

## Поведение

- можно создать пользователя;
- можно получить список пользователей;
- можно создать todo только для существующего пользователя;
- можно получить список todo.



