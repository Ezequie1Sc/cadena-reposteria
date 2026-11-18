"""Disponibilidad pública y diagnóstico de base de datos administrativo."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.core.auth import DbSession
from app.core.permissions import AdminUser

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check():
    return {"status": "ok", "message": "API funcionando correctamente"}


@router.get("/health/database")
def database_health(db: DbSession, admin: AdminUser):
    try:
        db.execute(text("SELECT 1")).scalar_one()
        return {"status": "ok", "database": "connected", "provider": "Supabase"}
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="No fue posible consultar la base de datos de Supabase",
        ) from None
