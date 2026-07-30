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
    # Base URL for the OpenAI-compatible endpoint. Empty = real OpenAI.
    # Set to https://integrate.api.nvidia.com/v1 to use NVIDIA NIM (same wire API).
    openai_base_url: str = ""
    # Per-request timeout (seconds) for each LLM HTTP call, so a hung or queued
    # provider connection fails fast instead of tying up the request for minutes.
    openai_timeout: float = 240.0
    openai_model_mini: str = "gpt-5-mini"
    openai_model_strong: str = "gpt-5"

    @property
    def db_path(self) -> Path:
        return self.myhub_data_dir / "myhub.db"


settings = Settings()
