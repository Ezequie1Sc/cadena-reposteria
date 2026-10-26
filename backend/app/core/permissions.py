
"""Autorización basada en roles para endpoints protegidos."""

from enum import IntEnum
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, DbSession
from app.modules.users.model import User


class RoleID(IntEnum):
    """Identificadores de roles registrados en PostgreSQL."""

    ADMINISTRADOR = 1
    EMPLEADO = 2
    CLIENTE = 3


def require_roles(*allowed_roles: RoleID):
    """
    Crea una dependencia que permite únicamente
    los roles indicados.

    La autenticación y el estado activo del usuario
    y su rol se verifican mediante CurrentUser.
    """

    if not allowed_roles:
        raise ValueError(
            "Debe especificarse al menos un rol permitido"
        )

    allowed_role_ids = frozenset(
        int(role) for role in allowed_roles
    )

    def check_permissions(
        current_user: CurrentUser,
    ) -> User:
        """Comprueba que el usuario tenga un rol autorizado."""

        if current_user.rol_id not in allowed_role_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "No tienes permisos para realizar "
                    "esta operación"
                ),
            )

        return current_user

    return check_permissions


# ============================================================
# DEPENDENCIAS REUTILIZABLES
# ============================================================


AdminUser = Annotated[
    User,
    Depends(require_roles(RoleID.ADMINISTRADOR)),
]

StaffUser = Annotated[
    User,
    Depends(
        require_roles(
            RoleID.ADMINISTRADOR,
            RoleID.EMPLEADO,
        )
    ),
]
