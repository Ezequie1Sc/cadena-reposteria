
"""Dependencias de autenticación para endpoints protegidos."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import Boolean, column, select, table
from sqlalchemy.orm import Session

from app.core.jwt import TokenValidationError, decode_access_token
from app.db.session import get_db
from app.modules.users.model import User
from app.modules.users.repository import user_repository
from app.shared.models.role_reference import roles_reference


# Extrae credenciales del encabezado Authorization: Bearer.
# auto_error=False permite unificar los errores de autenticación.
bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]

BearerCredentials = Annotated[
    HTTPAuthorizationCredentials | None,
    Depends(bearer_scheme),
]


def authentication_error() -> HTTPException:
    """Construye una respuesta HTTP 401 estándar."""

    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar la autenticación",
        headers={"WWW-Authenticate": "Bearer"},
    )


def validate_active_role(db: Session, role_id: int) -> None:
    """Comprueba que el rol del usuario exista y esté activo."""

    role_exists = db.scalar(
        select(roles_reference.c.id).where(
            roles_reference.c.id == role_id
        )
    )

    if role_exists is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El usuario no tiene un rol válido",
        )

    # La tabla real tiene 'activo', pero la referencia
    # SQLAlchemy solamente declara la columna 'id'.
    roles_table = table(
        "roles",
        column("id"),
        column("activo", Boolean),
    )

    is_active = db.scalar(
        select(roles_table.c.activo).where(
            roles_table.c.id == role_id
        )
    )

    if is_active is not True:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El rol del usuario está inactivo",
        )


def get_current_user(
    db: DbSession,
    credentials: BearerCredentials,
) -> User:
    """
    Obtiene el usuario autenticado a partir de su JWT.

    Rechaza credenciales inválidas, usuarios inactivos
    y roles inexistentes o desactivados.
    """

    if credentials is None:
        raise authentication_error()

    if credentials.scheme.lower() != "bearer":
        raise authentication_error()

    try:
        user_id = decode_access_token(
            credentials.credentials
        )
    except TokenValidationError as exc:
        raise authentication_error() from exc

    user = user_repository.get_by_id(
        db,
        user_id,
    )

    if user is None or not user.activo:
        raise authentication_error()

    validate_active_role(
        db,
        user.rol_id,
    )

    return user


CurrentUser = Annotated[
    User,
    Depends(get_current_user),
]
