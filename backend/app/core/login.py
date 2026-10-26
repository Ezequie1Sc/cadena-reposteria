
"""Servicio de autenticación mediante correo y contraseña."""

from dataclasses import dataclass

from argon2.exceptions import VerificationError
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import validate_active_role
from app.core.jwt import create_access_token
from app.core.security import verify_password
from app.modules.users.model import User
from app.modules.users.repository import user_repository


@dataclass(frozen=True)
class LoginResult:
    """Resultado de una autenticación exitosa."""

    access_token: str
    token_type: str = "bearer"


def invalid_credentials() -> HTTPException:
    """Genera una respuesta uniforme de autenticación fallida."""

    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Correo electrónico o contraseña incorrectos",
        headers={"WWW-Authenticate": "Bearer"},
    )


def authenticate_user(
    db: Session,
    *,
    email: str,
    password: str,
) -> User:
    """
    Autentica un usuario mediante correo y contraseña.

    Comprueba las credenciales y que tanto la cuenta
    como su rol se encuentren activos.

    No revela al cliente si una cuenta existe,
    está desactivada o tiene un rol inválido.
    """

    normalized_email = email.strip().lower()

    if not normalized_email or not password:
        raise invalid_credentials()

    user = user_repository.get_by_email(
        db,
        normalized_email,
    )

    if user is None:
        raise invalid_credentials()

    try:
        password_is_valid = verify_password(
            password,
            user.password_hash,
        )
    except (VerificationError, ValueError):
        raise invalid_credentials() from None

    if not password_is_valid:
        raise invalid_credentials()

    if not user.activo:
        raise invalid_credentials()

    try:
        validate_active_role(db, user.rol_id)
    except HTTPException:
        raise invalid_credentials() from None

    return user


def login_user(
    db: Session,
    *,
    email: str,
    password: str,
) -> LoginResult:
    """Autentica al usuario y genera su token JWT de acceso."""

    user = authenticate_user(
        db,
        email=email,
        password=password,
    )

    access_token = create_access_token(user.id)

    return LoginResult(
        access_token=access_token,
    )
