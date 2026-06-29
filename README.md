#  ToDo App: FastAPI + archtool DI

Минимальный рабочий FastAPI-проект с archtool-based dependency injection и in-memory storage.

## Что здесь используется

- FastAPI
- archtool DependencyInjector
- AppModule
- repository/service layers
- DI через class annotations
- users/todos modules
- interfaces.py, repos.py, services.py

## Структура проекта

```text
app/
├── archtool_conf/
│   └── bundle_project.py
├── users/
│   ├── interfaces.py
│   ├── repos.py
│   └── services.py
└── todos/
    ├── interfaces.py
    ├── repos.py
    └── services.py

entrypoints/
└── run.py
```

## Запуск

```bash
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



