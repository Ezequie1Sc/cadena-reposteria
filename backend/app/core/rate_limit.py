
"""Servicio de limitación de solicitudes de autenticación."""

import hashlib
import hmac
import ipaddress
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.modules.auth.rate_limit_repository import (
    RateLimitResult,
    rate_limit_repository,
)


WINDOW_SECONDS = 60
EMAIL_IP_LIMIT = 5
IP_LIMIT = 30

SessionFactory = Callable[[], Session]


@dataclass(frozen=True)
class LoginRateLimitResult:
    """Resultado de evaluar los límites de autenticación."""

    allowed: bool
    retry_after: int = 0


def _client_ip(request: Request) -> str:
    """
    Obtiene la dirección del cliente desde la conexión.

    No confía directamente en X-Forwarded-For, ya que
    ese encabezado puede ser falsificado.
    """
    if request.client is None:
        return "unknown"

    host = request.client.host

    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        return host


def _rate_limit_key(*, category: str, identifier: str) -> str:
    """Genera una clave HMAC para proteger el identificador."""

    message = f"{category}:{identifier}".encode("utf-8")

    digest = hmac.new(
        settings.jwt_secret_key.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()

    return f"{category}:{digest}"


@contextmanager
def _rate_limit_session(
    session_factory: SessionFactory,
) -> Iterator[Session]:
    """Administra una sesión exclusiva para los contadores."""

    with session_factory() as db:
        yield db


def check_login_rate_limit(
    *,
    request: Request,
    email: str,
    session_factory: SessionFactory = SessionLocal,
) -> LoginRateLimitResult:
    """
    Contabiliza una solicitud de autenticación.

    La sesión de los contadores es independiente de la
    sesión que consulta las credenciales del usuario.
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

    with _rate_limit_session(session_factory) as db:
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
    session_factory: SessionFactory = SessionLocal,
) -> None:
    """Rechaza solicitudes que superen los límites establecidos."""

    result = check_login_rate_limit(
        request=request,
        email=email,
        session_factory=session_factory,
    )

    if not result.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Demasiados intentos de inicio de sesión. "
                "Intenta más tarde."
            ),
            headers={
                "Retry-After": str(result.retry_after),
            },
        )
