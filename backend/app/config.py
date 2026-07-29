from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    myhub_password: str = "changeme"
    myhub_secret_key: str = "dev-secret-change-in-prod"
    myhub_env: str = "development"  # set to "production" in real deploys
    myhub_data_dir: Path = Path("data")
    myhub_static_dir: Path = Path("static")
    myhub_cookie_secure: bool = False
    mfds_api_key: str = ""
    openai_api_key: str = ""
    openai_model_mini: str = "gpt-5-mini"

    @property
    def db_path(self) -> Path:
        return self.myhub_data_dir / "myhub.db"


settings = Settings()
