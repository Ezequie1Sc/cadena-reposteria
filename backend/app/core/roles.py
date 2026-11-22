"""Contrato público de roles. Los permisos requieren que coincida el catálogo vigente."""

from enum import IntEnum

from sqlalchemy import Boolean, column, select, table
from sqlalchemy.orm import Session


class RoleID(IntEnum):
    ADMINISTRADOR = 1
    EMPLEADO = 2
    CLIENTE = 3

    @property
    def catalog_name(self) -> str:
        return self.name.capitalize()


def _role_table(schema=None):
    return table(
        "roles",
        column("id"),
        column("nombre"),
        column("activo", Boolean),
        schema=schema,
    )


_public_roles = _role_table("public")
_local_roles = _role_table()


def catalog_role_active(
    db: Session, role_id: int, *, lock: bool = False
) -> bool | None:
    """None indica un ID desconocido, ausente o asociado a un nombre incompatible."""
    try:
        role = RoleID(role_id)
    except ValueError:
        return None
    catalog = (
        _public_roles if db.get_bind().dialect.name == "postgresql" else _local_roles
    )
    query = select(catalog.c.activo).where(
        catalog.c.id == role.value, catalog.c.nombre == role.catalog_name
    )
    if lock:
        query = query.with_for_update(read=True)
    return db.scalar(query)
