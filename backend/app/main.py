from contextlib import asynccontextmanager

from fastapi import FastAPI

from .db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="MyHub", lifespan=lifespan)

    @app.get("/api/health")
    def health():
        return {"ok": True}

    return app


app = create_app()
