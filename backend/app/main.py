from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import settings
from .db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    from .db import SessionLocal
    from .seed import seed_evidence_and_limits, seed_metric_definitions
    db = SessionLocal()
    try:
        seed_metric_definitions(db)
        seed_evidence_and_limits(db)
    finally:
        db.close()

    yield


def create_app() -> FastAPI:
    defaults_in_use = (
        settings.myhub_secret_key == "dev-secret-change-in-prod"
        or settings.myhub_password == "changeme"
    )
    if defaults_in_use and (settings.myhub_cookie_secure or settings.myhub_env != "development"):
        raise RuntimeError(
            "Production (MYHUB_COOKIE_SECURE=true or MYHUB_ENV!=development) "
            "requires MYHUB_SECRET_KEY and MYHUB_PASSWORD to be set to "
            "non-default values."
        )

    app = FastAPI(title="MyHub", lifespan=lifespan)

    from . import auth
    auth.reset_login_attempts()
    app.include_router(auth.router)
    app.include_router(auth.profile_router)

    from .routers import analysis, calendar, chat, meals, metrics, photos, safety, supplements
    app.include_router(meals.router)
    app.include_router(metrics.router)
    app.include_router(supplements.router)
    app.include_router(calendar.router)
    app.include_router(safety.router)
    app.include_router(analysis.router)
    app.include_router(photos.router)
    app.include_router(chat.router)

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

        static_root = static_dir.resolve()

        @app.get("/{path:path}")
        def spa(path: str):
            candidate = (static_dir / path).resolve()
            if (path and candidate.is_file()
                    and candidate.is_relative_to(static_root)):
                return FileResponse(candidate)
            return FileResponse(static_dir / "index.html")

    return app


app = create_app()
