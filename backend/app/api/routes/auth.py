
"""Endpoints de autenticación y registro de usuarios."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.login import login_user
from app.core.rate_limit import (
    SessionFactory,
    enforce_login_rate_limit,
    enforce_registration_rate_limit,
)
from app.db.session import SessionLocal, get_db
from app.modules.auth.registration_schemas import (
    CustomerRegistrationRequest,
    CustomerRegistrationResponse,
)
from app.modules.auth.registration_service import (
    customer_registration_service,
)


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


DbSession = Annotated[
    Session,
    Depends(get_db),
]


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


@router.post(
    "/register",
    response_model=CustomerRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar cliente",
    description=(
        "Permite crear una cuenta de cliente sin autenticación previa. "
        "Asigna automáticamente el rol Cliente, almacena la contraseña "
        "mediante Argon2id y limita las solicitudes por IP."
    ),
    responses={
        409: {
            "description": (
                "Ya existe un usuario con el correo electrónico indicado"
            )
        },
        422: {
            "description": "Datos de registro inválidos"
        },
        429: {
            "description": (
                "Demasiadas solicitudes de registro. "
                "Incluye la cabecera Retry-After."
            )
        },
        503: {
            "description": (
                "El registro no está disponible porque el rol "
                "Cliente no existe o está inactivo"
            )
        },
    },
)
def register_customer(
    data: CustomerRegistrationRequest,
    request: Request,
    db: DbSession,
    rate_limit_session_factory: RateLimitSessionFactory,
) -> CustomerRegistrationResponse:
    """Registra una cuenta de cliente con protección por IP."""

    enforce_registration_rate_limit(
        request=request,
        session_factory=rate_limit_session_factory,
    )

    return customer_registration_service.register_customer(
        db=db,
        data=data,
    )
