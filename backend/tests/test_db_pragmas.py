from sqlalchemy import create_engine, event


def test_sqlite_pragmas_applied(tmp_path):
    # WAL + busy_timeout let the reminder scheduler's background-thread
    # writes coexist with request-handling writes instead of raising
    # "database is locked" on any overlap. Uses a real file-backed engine
    # (not the app's shared in-memory test engine) since WAL requires a file.
    from app.db import _set_sqlite_pragmas

    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    event.listens_for(engine, "connect")(_set_sqlite_pragmas)

    with engine.connect() as conn:
        journal_mode = conn.exec_driver_sql("PRAGMA journal_mode").scalar()
        busy_timeout = conn.exec_driver_sql("PRAGMA busy_timeout").scalar()

    engine.dispose()
    assert journal_mode == "wal"
    assert busy_timeout == 30000
