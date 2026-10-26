
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
    """Respuesta paginada de usuarios."""

    items: list[UserResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


@router.get(
    "",
    response_model=PaginatedUsersResponse,
    summary="Listar usuarios",
    description="Consulta usuarios con filtros y paginación.",
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos"},
        422: {"description": "Parámetros inválidos"},
    },
)
def list_users(
    db: DbSession,
    admin: AdminUser,
    busqueda: Annotated[
        str | None,
        Query(max_length=254),
    ] = None,
    rol_id: Annotated[
        int | None,
        Query(gt=0),
    ] = None,
    solo_activos: Annotated[
        bool | None,
        Query(),
    ] = True,
    page: Annotated[
        int,
        Query(ge=1),
    ] = 1,
    page_size: Annotated[
        int,
        Query(ge=1, le=100),
    ] = 20,
) -> PaginatedUsersResponse:
    """Lista usuarios autorizados para administración."""

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
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos"},
        404: {"description": "Usuario no encontrado"},
        422: {"description": "Identificador inválido"},
    },
)
def get_user(
    user_id: UserID,
    db: DbSession,
    admin: AdminUser,
) -> UserResponse:
    """Obtiene los datos públicos de un usuario."""

    return user_service.get_user_by_id(
        db=db,
        user_id=user_id,
    )


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear usuario",
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos"},
        409: {"description": "Conflicto de datos"},
        422: {"description": "Datos inválidos"},
    },
)
def create_user(
    data: UserCreate,
    db: DbSession,
    admin: AdminUser,
) -> UserResponse:
    """Registra un usuario con contraseña protegida."""

    return user_service.create_user(
        db=db,
        data=data,
    )


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Actualizar usuario",
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "Operación prohibida"},
        404: {"description": "Usuario no encontrado"},
        409: {"description": "Conflicto administrativo o de datos"},
        422: {"description": "Datos inválidos"},
    },
)
def update_user(
    user_id: UserID,
    data: UserUpdate,
    db: DbSession,
    admin: AdminUser,
) -> UserResponse:
    """Actualiza un usuario respetando las reglas administrativas."""

    return user_service.update_user(
        db=db,
        user_id=user_id,
        data=data,
        actor_id=admin.id,
    )


@router.delete(
    "/{user_id}",
    response_model=UserResponse,
    summary="Desactivar usuario",
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "Autodesactivación prohibida"},
        404: {"description": "Usuario no encontrado"},
        409: {"description": "Último administrador activo"},
        422: {"description": "Identificador inválido"},
    },
)
def deactivate_user(
    user_id: UserID,
    db: DbSession,
    admin: AdminUser,
) -> UserResponse:
    """Desactiva un usuario sin eliminarlo físicamente."""

    return user_service.deactivate_user(
        db=db,
        user_id=user_id,
        actor_id=admin.id,
    )


@router.patch(
    "/{user_id}/reactivar",
    response_model=UserResponse,
    summary="Reactivar usuario",
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos"},
        404: {"description": "Usuario no encontrado"},
        409: {"description": "Conflicto de datos"},
        422: {"description": "Rol inválido o inactivo"},
    },
)
def reactivate_user(
    user_id: UserID,
    db: DbSession,
    admin: AdminUser,
) -> UserResponse:
    """Reactiva un usuario si su rol continúa activo."""

    return user_service.reactivate_user(
        db=db,
        user_id=user_id,
    )
