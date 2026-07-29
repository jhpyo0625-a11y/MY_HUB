import pytest

from app.config import settings
from app.main import create_app


def test_prod_requires_secrets(monkeypatch):
    monkeypatch.setattr(settings, "myhub_cookie_secure", True)
    with pytest.raises(RuntimeError):
        create_app()

    monkeypatch.setattr(settings, "myhub_secret_key", "a-long-random-string")
    monkeypatch.setattr(settings, "myhub_password", "a-strong-password")
    create_app()  # does not raise


def test_env_production_requires_secrets_even_without_cookie_secure(monkeypatch):
    monkeypatch.setattr(settings, "myhub_cookie_secure", False)
    monkeypatch.setattr(settings, "myhub_env", "production")
    with pytest.raises(RuntimeError):
        create_app()

    monkeypatch.setattr(settings, "myhub_secret_key", "a-long-random-string")
    monkeypatch.setattr(settings, "myhub_password", "a-strong-password")
    create_app()  # does not raise
