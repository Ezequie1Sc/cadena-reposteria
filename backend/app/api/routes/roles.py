"""Catálogo de roles para administración mediante SQLAlchemy."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import Boolean, column, select, table
from sqlalchemy.exc import SQLAlchemyError
from app.core.auth import DbSession
from app.core.permissions import AdminUser

router = APIRouter(prefix="/roles", tags=["Roles"])
roles_table = table(
    "roles",
    column("id"),
    column("nombre"),
    column("descripcion"),
    column("activo", Boolean),
)


@router.get("", operation_id="listar_roles_activos", summary="Listar roles activos")
def get_roles(db: DbSession, admin: AdminUser):
    try:
        rows = (
            db.execute(
                select(roles_table)
                .where(roles_table.c.activo.is_(True))
                .order_by(roles_table.c.id)
            )
            .mappings()
            .all()
        )
        return {"total": len(rows), "roles": [dict(row) for row in rows]}
    except SQLAlchemyError:
        raise HTTPException(
            status_code=502, detail="No fue posible consultar los roles en Supabase"
        ) from None
