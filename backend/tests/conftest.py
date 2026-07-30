import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import create_app


@pytest.fixture()
def db_session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import app.models  # noqa: F401 — register tables (module exists from Task 2 on)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False)
    engine.dispose()


@pytest.fixture()
def client(db_session_factory):
    app = create_app()

    def override_get_db():
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    # plain TestClient (no `with`) does NOT run lifespan — no file DB side effects in tests
    return TestClient(app)


@pytest.fixture()
def auth_client(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "myhub_password", "changeme")
    res = client.post("/api/auth/login", json={"password": "changeme"})
    assert res.status_code == 200
    return client
