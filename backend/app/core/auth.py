"""Dependencias de autenticación para endpoints protegidos."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.jwt import TokenValidationError, verified_claims
from app.db.session import get_db
from app.modules.users.model import User
from app.modules.users.repository import user_repository
from app.core.roles import catalog_role_active


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

    is_active = catalog_role_active(db, role_id)
    if is_active is None:
        raise HTTPException(status_code=403, detail="El usuario no tiene un rol válido")

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
        claims = verified_claims(credentials.credentials)
        user_id = int(claims["sub"])
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

    from app.modules.administracion.access import check_employee_session

    check_employee_session(db, user)
    # Also enforce the cutoff when the rollout flag is switched off after activation.
    if db.get_bind().dialect.name == "postgresql":
        cutoff = db.scalar(
            text("""SELECT max(v.fecha) FROM gestion_interna.evento v
            JOIN public.empleados e ON e.id=v.empleado_id
            WHERE e.usuario_id=:id AND v.accion='REVOCADO'"""),
            {"id": user.id},
        )
        if cutoff and claims["iat"] <= cutoff.timestamp():
            raise authentication_error()
    return user


CurrentUser = Annotated[
    User,
    Depends(get_current_user),
]
