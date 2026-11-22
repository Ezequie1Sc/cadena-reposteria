"""Configuración validada; nunca contiene credenciales predeterminadas."""

from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    administracion_habilitada: bool = False
    correo_clave_cifrado: str | None = Field(default=None, repr=False)
    resend_api_key: str | None = Field(default=None, repr=False)
    correo_remitente: str | None = None
    portal_url: str | None = None
    supabase_storage_key: str | None = Field(default=None, repr=False)
    app_name: str = "Sistema de Gestión de Repostería"
    app_env: Literal["development", "test", "staging", "production"] = "development"
    debug: bool = False
    database_url: str = Field(repr=False)
    # Optional migration-only credential. DATABASE_URL is never rewritten.
    migration_database_url: str | None = Field(default=None, repr=False)
    # Legacy optional integration, not used by API routes.
    supabase_url: str | None = None
    supabase_key: str | None = Field(default=None, repr=False)
    jwt_secret_key: str = Field(min_length=32, repr=False)
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=30, ge=1, le=1440)
    cors_origins: list[str] = Field(default_factory=list)
    docs_enabled: bool = True

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_secret(cls, value: str) -> str:
        if len(set(value)) < 12 or value.lower().startswith(
            ("change", "replace", "cambiar", "reemplazar")
        ):
            raise ValueError("Genera una clave JWT aleatoria de al menos 32 caracteres")
        return value

    @field_validator("cors_origins")
    @classmethod
    def validate_origins(cls, values: list[str]) -> list[str]:
        for origin in values:
            parts = urlsplit(origin)
            if (
                parts.scheme not in {"http", "https"}
                or not parts.netloc
                or parts.username
                or parts.password
                or parts.path
                or parts.query
                or parts.fragment
            ):
                raise ValueError(
                    "CORS requiere orígenes explícitos sin rutas ni comodines"
                )
        return values

    @model_validator(mode="after")
    def production_settings(self):
        if self.app_env in {"staging", "production"} and self.debug:
            raise ValueError("DEBUG debe ser false fuera de desarrollo")
        return self


settings = Settings()
