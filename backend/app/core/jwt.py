
"""Generación y validación de tokens JWT de acceso."""

from datetime import datetime, timedelta, timezone

import jwt
from jwt import InvalidTokenError

from app.core.config import settings


class TokenValidationError(Exception):
    """Indica que un token es inválido o ha expirado."""


def create_access_token(
    user_id: int,
    expires_delta: timedelta | None = None,
) -> str:
    """Genera un JWT firmado para un usuario."""

    if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
        raise ValueError("El identificador de usuario debe ser positivo")

    now = datetime.now(timezone.utc)

    duration = (
        expires_delta
        if expires_delta is not None
        else timedelta(
            minutes=settings.jwt_access_token_expire_minutes
        )
    )

    if duration <= timedelta(0):
        raise ValueError("La duración del token debe ser positiva")

    payload = {
        "sub": str(user_id),
        "iat": now,
        "nbf": now,
        "exp": now + duration,
        "type": "access",
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> int:
    """
    Verifica la firma, las fechas y el tipo de token.

    Devuelve el identificador del usuario autenticado.
    """

    if not isinstance(token, str) or not token.strip():
        raise TokenValidationError("Token de acceso inválido")

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={
                "require": [
                    "sub",
                    "iat",
                    "nbf",
                    "exp",
                    "type",
                ],
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "verify_nbf": True,
            },
            leeway=0,
        )

    except InvalidTokenError as exc:
        raise TokenValidationError(
            "Token de acceso inválido o expirado"
        ) from exc

    if payload.get("type") != "access":
        raise TokenValidationError("Tipo de token no permitido")

    subject = payload.get("sub")

    if (
        not isinstance(subject, str)
        or not subject.isascii()
        or not subject.isdecimal()
    ):
        raise TokenValidationError("Identificador de usuario inválido")

    user_id = int(subject)

    if user_id <= 0:
        raise TokenValidationError("Identificador de usuario inválido")

    return user_id
