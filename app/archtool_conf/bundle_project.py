from pathlib import Path

from archtool.dependency_injector import DependencyInjector
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from web_fractal.building_utils import filter_objects_of_type
from web_fractal.db import Base
from web_fractal.http.interfaces import HttpControllerABC

from app.archtool_conf.custom_layers import APPS, app_layers
from app.config import DATABASE_URL

PROJECT_ROOT = Path(__file__).resolve().parents[2]

engine = create_async_engine(DATABASE_URL, echo=False)
session_maker = async_sessionmaker(engine, expire_on_commit=False)

injector = DependencyInjector(
    modules_list=APPS,
    layers=app_layers,
    project_root=PROJECT_ROOT,
)
injector.register(key=AsyncEngine, value=engine, inject_into=False)
injector.register(key=async_sessionmaker, value=session_maker, inject_into=False)
injector.inject()
injector._dependencies = injector.dependencies


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def init_app(app: FastAPI) -> None:
    controllers = filter_objects_of_type(injector, HttpControllerABC)
    for controller in controllers:
        controller.init_http_routes()
        app.include_router(controller.router)


__all__ = ["init_db", "init_app", "injector", "session_maker", "engine"]
