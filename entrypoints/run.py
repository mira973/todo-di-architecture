from fastapi import FastAPI, HTTPException

from app.archtool_conf.bundle_project import init_app, init_db

app = FastAPI(title="Todo App", version="1.0.0")
init_app(app)


@app.on_event("startup")
async def startup() -> None:
    await init_db()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("entrypoints.run:app", host="127.0.0.1", port=8000, reload=True)