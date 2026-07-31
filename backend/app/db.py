from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


def _set_sqlite_pragmas(dbapi_connection, connection_record):
    # The reminder scheduler (Phase 3) writes from a background thread every
    # minute, independent of request-handling threads. SQLite's default
    # busy behavior raises "database is locked" immediately on any overlap
    # instead of waiting — WAL mode + a busy_timeout let a second writer wait
    # briefly for the lock instead of hard-failing the request.
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()


engine = create_engine(
    f"sqlite:///{settings.db_path}",
    connect_args={"check_same_thread": False},
)
event.listens_for(engine, "connect")(_set_sqlite_pragmas)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from . import models  # noqa: F401 — register tables

    settings.myhub_data_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)
