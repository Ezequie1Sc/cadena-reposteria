
"""Configuración central de la aplicación."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Variables de configuración de la API."""

    app_name: str = "Sistema de Gestión de Repostería"
    app_env: str = "development"
    debug: bool = True

    # Conexión directa a PostgreSQL
    database_url: str

    # Cliente Supabase existente
    supabase_url: str | None = None
    supabase_key: str | None = None

    # Autenticación JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
