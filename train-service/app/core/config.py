# app/core/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional
from urllib.parse import quote_plus


class Settings(BaseSettings):
    # App
    app_name: str = "AthletIQ Train Service"
    app_version: str = "1.0.0"
    debug: bool = True

    # Database
    db_host: str
    db_port: int = 5432
    db_user: str
    db_password: str
    db_name: str
    db_sslmode: str = "require"

    # 🔥 Schema per service
    db_schema: str = "train"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379

    # Core Service
    core_service_url: str

    # JWT
    jwt_secret_key: str
    jwt_algorithm: str

    # ============================================================
    # IA Configuration for CU-TRAIN-04 (Premium feature)
    # ============================================================
    # Enable/disable IA workout generation
    ia_enabled: bool = False
    
    # External IA service API endpoint (e.g., OpenAI, Gemini, custom service)
    ia_api_url: Optional[str] = None
    
    # API key for external IA service
    ia_api_key: Optional[str] = None
    
    # Maximum number of IA calls per week (rate limiting)
    ia_max_calls_per_week: int = 1

    # Configuración moderna (Pydantic v2)
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="forbid"
    )

    @property
    def database_url(self) -> str:
        """Build PostgreSQL connection URL with proper escaping."""
        password = quote_plus(self.db_password)

        url = (
            f"postgresql+psycopg2://{self.db_user}:{password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
            f"?options=-csearch_path={self.db_schema}"
        )

        # Only add SSL if needed
        if self.db_sslmode and self.db_sslmode != "disable":
            url += f"&sslmode={self.db_sslmode}"

        # Only useful for cloud deployments
        if self.db_host != "localhost":
            url += "&target_session_attrs=read-write"

        return url


@lru_cache
def get_settings() -> Settings:
    """Singleton settings instance."""
    return Settings()


settings = get_settings()