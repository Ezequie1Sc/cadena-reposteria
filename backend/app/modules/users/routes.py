
"""Endpoints administrativos para la gestión de usuarios."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.permissions import AdminUser
from app.db.session import get_db
from app.modules.users.schemas import (
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.modules.users.service import user_service


router = APIRouter(
    prefix="/usuarios",
    tags=["Usuarios"],
)


DbSession = Annotated[Session, Depends(get_db)]

UserID = Annotated[
    int,
    Path(
        gt=0,
        description="Identificador del usuario",
    ),
]


class PaginatedUsersResponse(BaseModel):
    """Respuesta paginada del listado de usuarios."""

    items: list[UserResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


@router.get(
    "",
    response_model=PaginatedUsersResponse,
    summary="Listar usuarios",
    description=(
        "Consulta usuarios con búsqueda, filtros por rol "
        "y estado, y paginación. Requiere rol Administrador."
    ),
    responses={
        401: {"description": "Autenticación requerida"},
        403: {"description": "Permisos insuficientes"},
        422: {"description": "Parámetros inválidos"},
    },
)
def list_users(
    db: DbSession,
    admin: AdminUser,
    busqueda: Annotated[
        str | None,
        Query(
            max_length=254,
            description="Buscar por nombre, apellido o correo",
        ),
    ] = None,
    rol_id: Annotated[
        int | None,
        Query(
            gt=0,
            description="Filtrar por identificador de rol",
        ),
    ] = None,
    solo_activos: Annotated[
        bool | None,
        Query(
            description=(
                "True: activos; False: inactivos; "
                "omitir para usar el filtro predeterminado"
            ),
        ),
    ] = True,
    page: Annotated[
        int,
        Query(
            ge=1,
            description="Número de página",
        ),
    ] = 1,
    page_size: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            description="Usuarios por página",
        ),
    ] = 20,
) -> PaginatedUsersResponse:
    """Devuelve usuarios según los filtros solicitados."""

    result = user_service.get_users(
        db=db,
        busqueda=busqueda,
        rol_id=rol_id,
        solo_activos=solo_activos,
        page=page,
        page_size=page_size,
    )

    return PaginatedUsersResponse.model_validate(result)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Consultar usuario",
    description=(
        "Obtiene la información de un usuario por ID. "
        "Requiere rol Administrador."
    ),
    responses={
        401: {"description": "Autenticación requerida"},
        403: {"description": "Permisos insuficientes"},
        404: {"description": "Usuario no encontrado"},
        422: {"description": "Identificador inválido"},
    },
)
def get_user(
    user_id: UserID,
    db: DbSession,
    admin: AdminUser,
) -> UserResponse:
    """Consulta un usuario específico."""

    return user_service.get_user_by_id(
        db=db,
        user_id=user_id,
    )


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear usuario",
    description=(
        "Registra un usuario con contraseña protegida "
        "mediante Argon2id. Requiere rol Administrador."
    ),
    responses={
        401: {"description": "Autenticación requerida"},
        403: {"description": "Permisos insuficientes"},
        409: {"description": "Correo electrónico duplicado"},
        422: {"description": "Datos o rol inválidos"},
    },
)
def create_user(
    data: UserCreate,
    db: DbSession,
    admin: AdminUser,
) -> UserResponse:
    """Registra un usuario en el sistema."""

    return user_service.create_user(
        db=db,
        data=data,
    )


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Actualizar usuario",
    description=(
        "Actualiza parcialmente los datos de un usuario. "
        "Requiere rol Administrador."
    ),
    responses={
        401: {"description": "Autenticación requerida"},
        403: {"description": "Permisos insuficientes"},
        404: {"description": "Usuario no encontrado"},
        409: {"description": "Conflicto de datos"},
        422: {"description": "Datos inválidos"},
    },
)
def update_user(
    user_id: UserID,
    data: UserUpdate,
    db: DbSession,
    admin: AdminUser,
) -> UserResponse:
    """Actualiza los campos proporcionados."""

    return user_service.update_user(
        db=db,
        user_id=user_id,
        data=data,
    )


@router.delete(
    "/{user_id}",
    response_model=UserResponse,
    summary="Desactivar usuario",
    description=(
        "Desactiva una cuenta sin eliminar sus datos. "
        "Requiere rol Administrador."
    ),
    responses={
        401: {"description": "Autenticación requerida"},
        403: {"description": "Permisos insuficientes"},
        404: {"description": "Usuario no encontrado"},
        409: {"description": "Conflicto de datos"},
        422: {"description": "Identificador inválido"},
    },
)
def deactivate_user(
    user_id: UserID,
    db: DbSession,
    admin: AdminUser,
) -> UserResponse:
    """Desactiva lógicamente un usuario."""

    return user_service.deactivate_user(
        db=db,
        user_id=user_id,
    )


@router.patch(
    "/{user_id}/reactivar",
    response_model=UserResponse,
    summary="Reactivar usuario",
    description=(
        "Reactiva una cuenta siempre que su rol siga activo. "
        "Requiere rol Administrador."
    ),
    responses={
        401: {"description": "Autenticación requerida"},
        403: {"description": "Permisos insuficientes"},
        404: {"description": "Usuario no encontrado"},
        409: {"description": "Conflicto de datos"},
        422: {"description": "Identificador o rol inválido"},
    },
)
def reactivate_user(
    user_id: UserID,
    db: DbSession,
    admin: AdminUser,
) -> UserResponse:
    """Reactiva una cuenta previamente desactivada."""

    return user_service.reactivate_user(
        db=db,
        user_id=user_id,
    )
