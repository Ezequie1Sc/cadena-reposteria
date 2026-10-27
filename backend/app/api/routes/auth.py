
"""Endpoints de autenticación de usuarios."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.login import login_user
from app.core.rate_limit import (
    SessionFactory,
    enforce_login_rate_limit,
)
from app.db.session import SessionLocal, get_db


router = APIRouter(
    prefix="/auth",
    tags=["Autenticación"],
)


class LoginRequest(BaseModel):
    """Credenciales para iniciar sesión."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(
        min_length=1,
        max_length=254,
        description="Correo electrónico del usuario",
        examples=["admin@example.com"],
    )

    password: str = Field(
        min_length=1,
        description="Contraseña del usuario",
    )


class TokenResponse(BaseModel):
    """Token JWT de autenticación."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"


DbSession = Annotated[Session, Depends(get_db)]


def get_rate_limit_session_factory() -> SessionFactory:
    """Proporciona una fábrica de sesiones para los contadores."""

    return SessionLocal


RateLimitSessionFactory = Annotated[
    SessionFactory,
    Depends(get_rate_limit_session_factory),
]


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Iniciar sesión",
    description=(
        "Valida las credenciales del usuario y devuelve un token JWT "
        "de acceso. Aplica límites de solicitudes por IP y correo."
    ),
    responses={
        401: {
            "description": (
                "Credenciales incorrectas o cuenta no autorizada "
                "para iniciar sesión"
            )
        },
        422: {
            "description": "Datos de entrada inválidos"
        },
        429: {
            "description": (
                "Demasiadas solicitudes de autenticación. "
                "Incluye la cabecera Retry-After."
            )
        },
    },
)
def login(
    credentials: LoginRequest,
    request: Request,
    db: DbSession,
    rate_limit_session_factory: RateLimitSessionFactory,
) -> TokenResponse:
    """Autentica al usuario después de comprobar los límites."""

    enforce_login_rate_limit(
        request=request,
        email=credentials.email,
        session_factory=rate_limit_session_factory,
    )

    result = login_user(
        db,
        email=credentials.email,
        password=credentials.password,
    )

    return TokenResponse(
        access_token=result.access_token,
        token_type=result.token_type,
    )
