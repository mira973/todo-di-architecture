from __future__ import annotations

import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./todo.db")
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
