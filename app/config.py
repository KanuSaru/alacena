"""Configuración de la aplicación leída desde variables de entorno (.env)."""

import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self) -> None:
        self.app_env: str = os.getenv("APP_ENV", "development")
        self.database_url: str = os.getenv("DATABASE_URL", "sqlite:///./recetas.db")

        self.secret_key: str = os.getenv("SECRET_KEY", "")
        if not self.secret_key:
            if self.app_env == "production":
                raise RuntimeError("SECRET_KEY es obligatoria en producción")
            self.secret_key = "clave-solo-para-desarrollo"
        self.jwt_algorithm: str = "HS256"
        self.access_token_expire_minutes: int = int(
            os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
        )

        self.openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
        self.openrouter_model: str = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
        self.openrouter_base_url: str = os.getenv(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        ).rstrip("/")
        self.llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
        self.app_url: str = os.getenv("APP_URL", "http://localhost:8000")


settings = Settings()
