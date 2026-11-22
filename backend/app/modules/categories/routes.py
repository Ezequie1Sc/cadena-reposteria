from app.core.roles import RoleID
from app.core.auth import CurrentUser
from app.core.permissions import AdminUser

import logging
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    Response,
    status,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.categories.schemas import (
    CategoryCreate,
    CategoryListResponse,
    CategoryResponse,
    CategoryUpdate,
)
from app.modules.categories.service import category_service


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/categorias",
    tags=["Categorías"],
)

DbSession = Annotated[Session, Depends(get_db)]


@router.get(
    "",
    response_model=CategoryListResponse,
    summary="Listar categorías",
)
def get_categories(
    actor: CurrentUser,
    db: DbSession,
    busqueda: str | None = Query(
        default=None,
        min_length=1,
        max_length=100,
    ),
    solo_activos: bool = Query(
        default=True,
        description="Mostrar únicamente categorías activas",
    ),
):
    if actor.rol_id != RoleID.ADMINISTRADOR and not solo_activos:
        raise HTTPException(status_code=403, detail="Solo administración puede consultar inactivos")

    try:
        categories = category_service.get_categories(
            db=db,
            busqueda=busqueda,
            solo_activos=solo_activos,
        )

        return CategoryListResponse(
            total=len(categories),
            categorias=categories,
        )

    except SQLAlchemyError:
        logger.exception("Error al listar categorías")
        raise HTTPException(
            status_code=503,
            detail="No fue posible consultar las categorías",
        ) from None


@router.get(
    "/{category_id}",
    response_model=CategoryResponse,
    responses={404: {"description": "Categoría no encontrada"}},
    summary="Consultar categoría",
)
def get_category(
    actor: CurrentUser,
    db: DbSession,
    category_id: int = Path(gt=0),
):
    try:
        category = category_service.get_category_by_id(
            db=db,
            category_id=category_id,
        )

        if category is None or (actor.rol_id != RoleID.ADMINISTRADOR and not category.activo):
            raise HTTPException(
                status_code=404,
                detail="Categoría no encontrada",
            )

        return category

    except SQLAlchemyError:
        logger.exception(
            "Error al consultar categoría %s",
            category_id,
        )
        raise HTTPException(
            status_code=503,
            detail="No fue posible consultar la categoría",
        ) from None


@router.post(
    "",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear categoría",
)
def create_category(
    actor: AdminUser,
    data: CategoryCreate,
    db: DbSession,
):
    try:
        return category_service.create_category(
            db=db,
            data=data,
        )

    except SQLAlchemyError:
        db.rollback()
        logger.exception("Error al crear categoría")
        raise HTTPException(
            status_code=503,
            detail="No fue posible crear la categoría",
        ) from None


@router.patch(
    "/{category_id}",
    response_model=CategoryResponse,
    summary="Actualizar categoría",
)
def update_category(
    actor: AdminUser,
    data: CategoryUpdate,
    db: DbSession,
    category_id: int = Path(gt=0),
):
    try:
        return category_service.update_category(
            db=db,
            category_id=category_id,
            data=data,
        )

    except SQLAlchemyError:
        db.rollback()
        logger.exception(
            "Error al actualizar categoría %s",
            category_id,
        )
        raise HTTPException(
            status_code=503,
            detail="No fue posible actualizar la categoría",
        ) from None


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desactivar categoría",
    description=(
        "Desactiva una categoría sin eliminarla físicamente. "
        "No permite desactivar categorías con productos activos."
    ),
    responses={
        404: {"description": "Categoría no encontrada"},
        409: {"description": "La categoría tiene productos activos"},
    },
)
def deactivate_category(
    actor: AdminUser,
    db: DbSession,
    category_id: int = Path(gt=0),
):
    try:
        category_service.deactivate_category(
            db=db,
            category_id=category_id,
        )

        return Response(
            status_code=status.HTTP_204_NO_CONTENT,
        )

    except SQLAlchemyError:
        db.rollback()
        logger.exception(
            "Error al desactivar categoría %s",
            category_id,
        )
        raise HTTPException(
            status_code=503,
            detail="No fue posible desactivar la categoría",
        ) from None


@router.patch(
    "/{category_id}/reactivar",
    response_model=CategoryResponse,
    summary="Reactivar categoría",
)
def reactivate_category(
    actor: AdminUser,
    db: DbSession,
    category_id: int = Path(gt=0),
):
    try:
        return category_service.reactivate_category(
            db=db,
            category_id=category_id,
        )

    except SQLAlchemyError:
        db.rollback()
        logger.exception(
            "Error al reactivar categoría %s",
            category_id,
        )
        raise HTTPException(
            status_code=503,
            detail="No fue posible reactivar la categoría",
        ) from None
