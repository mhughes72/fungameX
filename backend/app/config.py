from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    # Storage. Local default is SQLite; Railway provides a postgres:// URL.
    database_url: str = f"sqlite:///{(BASE_DIR / 'data' / 'app.db').as_posix()}"
    # If set, jobs go through RQ and the separate worker process runs them.
    # If empty, jobs run on threads inside the API process (local dev).
    redis_url: str = ""
    # "sync" runs jobs inline (tests only).
    jobs_mode_override: str = ""

    # Auth (single user)
    app_password: str = "changeme"
    secret_key: str = "dev-secret-change-me"
    session_max_age_days: int = 30
    cookie_secure: bool = False

    # OpenAI
    openai_api_key: str = ""
    openai_model_fast: str = "gpt-5-mini"
    openai_model_writer: str = "gpt-5"
    openai_moderation_model: str = "omni-moderation-latest"
    # USD per 1M tokens; used for cost logging and the budget cap. 0 = unknown.
    openai_price_fast_input: float = 0.0
    openai_price_fast_output: float = 0.0
    openai_price_writer_input: float = 0.0
    openai_price_writer_output: float = 0.0

    # Ingestion
    user_agent: str = "XPostGenerator/1.0 (+personal use; contact owner)"
    fetch_timeout_s: float = 20.0
    scheduler_tick_s: int = 60
    article_max_chars: int = 48000  # roughly 12k tokens

    @property
    def sqlalchemy_url(self) -> str:
        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        return url

    @property
    def jobs_mode(self) -> str:
        if self.jobs_mode_override:
            return self.jobs_mode_override
        return "rq" if self.redis_url else "thread"


@lru_cache
def get_settings() -> Settings:
    return Settings()
