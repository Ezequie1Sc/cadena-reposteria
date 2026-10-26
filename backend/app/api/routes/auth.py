
"""Endpoints de autenticación de usuarios."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.login import login_user
from app.db.session import get_db


router = APIRouter(
    prefix="/auth",
    tags=["Autenticación"],
)


# ============================================================
# ESQUEMAS
# ============================================================


class LoginRequest(BaseModel):
    """Credenciales necesarias para iniciar sesión."""

    model_config = ConfigDict(
        extra="forbid",
    )

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
    """Respuesta de autenticación exitosa."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"


# ============================================================
# DEPENDENCIAS
# ============================================================


DbSession = Annotated[
    Session,
    Depends(get_db),
]


# ============================================================
# ENDPOINTS
# ============================================================


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Iniciar sesión",
    description=(
        "Valida las credenciales del usuario y devuelve "
        "un token JWT de acceso."
    ),
    responses={
        401: {
            "description": (
                "Credenciales incorrectas o cuenta "
                "no autorizada para iniciar sesión"
            ),
        },
        422: {
            "description": "Datos de entrada inválidos",
        },
    },
)
def login(
    credentials: LoginRequest,
    db: DbSession,
) -> TokenResponse:
    """Autentica al usuario y devuelve su token de acceso."""

    result = login_user(
        db,
        email=credentials.email,
        password=credentials.password,
    )

    return TokenResponse(
        access_token=result.access_token,
        token_type=result.token_type,
    )
