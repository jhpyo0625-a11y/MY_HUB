from contextlib import asynccontextmanager

from fastapi import FastAPI

from .db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    from .db import SessionLocal
    from .seed import seed_metric_definitions
    db = SessionLocal()
    try:
        seed_metric_definitions(db)
    finally:
        db.close()

    yield


def create_app() -> FastAPI:
    app = FastAPI(title="MyHub", lifespan=lifespan)

    from . import auth
    app.include_router(auth.router)
    app.include_router(auth.profile_router)

    from .routers import meals, metrics
    app.include_router(meals.router)
    app.include_router(metrics.router)

    @app.get("/api/health")
    def health():
        return {"ok": True}

    return app


app = create_app()
