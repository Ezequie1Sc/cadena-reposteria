"""Integración heredada opcional; la API usa SQLAlchemy y no importa este cliente."""

from functools import lru_cache
from supabase import Client, create_client
from app.core.config import settings


@lru_cache
def get_supabase_client() -> Client:
    if not settings.supabase_url or not settings.supabase_key:
        raise RuntimeError("La integración opcional de Supabase no está configurada")
    return create_client(settings.supabase_url, settings.supabase_key)


def __getattr__(name: str):
    # Preserve the legacy import only when explicitly requested.
    if name == "supabase":
        return get_supabase_client()
    raise AttributeError(name)
