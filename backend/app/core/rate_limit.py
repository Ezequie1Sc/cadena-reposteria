
"""Servicio de limitación de solicitudes de autenticación."""

import hashlib
import hmac
import ipaddress
from dataclasses import dataclass

from fastapi import HTTPException, Request, status

from app.core.config import settings
from app.db.session import SessionLocal
from app.modules.auth.rate_limit_repository import (
    RateLimitResult,
    rate_limit_repository,
)


WINDOW_SECONDS = 60
EMAIL_IP_LIMIT = 5
IP_LIMIT = 30


@dataclass(frozen=True)
class LoginRateLimitResult:
    """Resultado de evaluar los límites de autenticación."""

    allowed: bool
    retry_after: int = 0


def _client_ip(request: Request) -> str:
    """
    Obtiene la dirección del cliente desde la conexión.

    No confía directamente en X-Forwarded-For porque ese
    encabezado puede ser falsificado por el solicitante.
    """
    if request.client is None:
        return "unknown"

    host = request.client.host

    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        return host


def _rate_limit_key(*, category: str, identifier: str) -> str:
    """Genera una clave HMAC sin exponer el identificador original."""

    message = f"{category}:{identifier}".encode("utf-8")

    digest = hmac.new(
        settings.jwt_secret_key.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()

    return f"{category}:{digest}"


def check_login_rate_limit(
    *,
    request: Request,
    email: str,
) -> LoginRateLimitResult:
    """
    Contabiliza la solicitud de inicio de sesión.

    Cada contador se actualiza en una sesión independiente
    de la sesión utilizada para autenticar al usuario.
    """

    ip = _client_ip(request)
    normalized_email = email.strip().lower()

    ip_key = _rate_limit_key(
        category="ip",
        identifier=ip,
    )

    email_ip_key = _rate_limit_key(
        category="email_ip",
        identifier=f"{ip}:{normalized_email}",
    )

    with SessionLocal() as db:
        ip_result: RateLimitResult = (
            rate_limit_repository.record_attempt(
                db,
                key=ip_key,
                limit=IP_LIMIT,
                window_seconds=WINDOW_SECONDS,
            )
        )

        if not ip_result.allowed:
            return LoginRateLimitResult(
                allowed=False,
                retry_after=ip_result.retry_after,
            )

        email_result: RateLimitResult = (
            rate_limit_repository.record_attempt(
                db,
                key=email_ip_key,
                limit=EMAIL_IP_LIMIT,
                window_seconds=WINDOW_SECONDS,
            )
        )

        if not email_result.allowed:
            return LoginRateLimitResult(
                allowed=False,
                retry_after=email_result.retry_after,
            )

    return LoginRateLimitResult(allowed=True)


def enforce_login_rate_limit(
    *,
    request: Request,
    email: str,
) -> None:
    """Rechaza solicitudes que superen los límites configurados."""

    result = check_login_rate_limit(
        request=request,
        email=email,
    )

    if not result.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos de inicio de sesión. Intenta más tarde.",
            headers={
                "Retry-After": str(result.retry_after),
            },
        )
