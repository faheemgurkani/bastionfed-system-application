from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_backend_env_path() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / ".env"
        if candidate.exists():
            return candidate
        if parent.name == "backend":
            return candidate
    return current.parents[1] / ".env"


BACKEND_ENV_PATH = _find_backend_env_path()
load_dotenv(BACKEND_ENV_PATH)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BACKEND_ENV_PATH), env_file_encoding="utf-8", extra="ignore")

    allowed_origins: str = "http://localhost:3000"
    api_title: str = "BastionFed API"
    bastionbot_db_path: str = "data/bastionbot.sqlite3"
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()
