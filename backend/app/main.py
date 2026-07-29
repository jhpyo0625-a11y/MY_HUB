from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import settings
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
    if settings.myhub_cookie_secure and (
        settings.myhub_secret_key == "dev-secret-change-in-prod"
        or settings.myhub_password == "changeme"
    ):
        raise RuntimeError(
            "Production (MYHUB_COOKIE_SECURE=true) requires MYHUB_SECRET_KEY "
            "and MYHUB_PASSWORD to be set to non-default values."
        )

    app = FastAPI(title="MyHub", lifespan=lifespan)

    from . import auth
    app.include_router(auth.router)
    app.include_router(auth.profile_router)

    from .routers import calendar, meals, metrics, supplements
    app.include_router(meals.router)
    app.include_router(metrics.router)
    app.include_router(supplements.router)
    app.include_router(calendar.router)

    @app.get("/api/health")
    def health():
        return {"ok": True}

    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    static_dir = settings.myhub_static_dir
    if static_dir.is_dir():
        if (static_dir / "assets").is_dir():
            app.mount("/assets", StaticFiles(directory=static_dir / "assets"),
                      name="assets")

        @app.get("/{path:path}")
        def spa(path: str):
            candidate = static_dir / path
            if path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(static_dir / "index.html")

    return app


app = create_app()
