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
from app.modules.branches.schemas import (
    BranchCreate,
    BranchListResponse,
    BranchResponse,
    BranchUpdate,
)
from app.modules.branches.service import branch_service


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/sucursales",
    tags=["Sucursales"],
)

DbSession = Annotated[Session, Depends(get_db)]


@router.get(
    "",
    response_model=BranchListResponse,
    summary="Listar sucursales",
)
def get_branches(
    actor: CurrentUser,
    db: DbSession,
    busqueda: str | None = Query(
        default=None,
        min_length=1,
        max_length=120,
    ),
    solo_activos: bool = Query(
        default=True,
        description="Mostrar únicamente sucursales activas",
    ),
):
    if actor.rol_id != RoleID.ADMINISTRADOR and not solo_activos:
        raise HTTPException(status_code=403, detail="Solo administración puede consultar inactivos")

    try:
        branches = branch_service.get_branches(
            db=db,
            busqueda=busqueda,
            solo_activos=solo_activos,
        )

        return BranchListResponse(
            total=len(branches),
            sucursales=branches,
        )

    except SQLAlchemyError:
        logger.exception("Error al listar sucursales")
        raise HTTPException(
            status_code=503,
            detail="No fue posible consultar las sucursales",
        ) from None


@router.get(
    "/{branch_id}",
    response_model=BranchResponse,
    responses={
        404: {"description": "Sucursal no encontrada"},
    },
    summary="Consultar sucursal",
)
def get_branch(
    actor: CurrentUser,
    db: DbSession,
    branch_id: int = Path(gt=0),
):
    try:
        branch = branch_service.get_branch_by_id(
            db=db,
            branch_id=branch_id,
        )

        if branch is None or (actor.rol_id != RoleID.ADMINISTRADOR and not branch.activo):
            raise HTTPException(
                status_code=404,
                detail="Sucursal no encontrada",
            )

        return branch

    except SQLAlchemyError:
        logger.exception(
            "Error al consultar sucursal %s",
            branch_id,
        )
        raise HTTPException(
            status_code=503,
            detail="No fue posible consultar la sucursal",
        ) from None


@router.post(
    "",
    response_model=BranchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear sucursal",
)
def create_branch(
    actor: AdminUser,
    data: BranchCreate,
    db: DbSession,
):
    try:
        return branch_service.create_branch(
            db=db,
            data=data,
        )

    except SQLAlchemyError:
        db.rollback()
        logger.exception("Error al crear sucursal")
        raise HTTPException(
            status_code=503,
            detail="No fue posible crear la sucursal",
        ) from None


@router.patch(
    "/{branch_id}",
    response_model=BranchResponse,
    summary="Actualizar sucursal",
)
def update_branch(
    actor: AdminUser,
    data: BranchUpdate,
    db: DbSession,
    branch_id: int = Path(gt=0),
):
    try:
        return branch_service.update_branch(
            db=db,
            branch_id=branch_id,
            data=data,
        )

    except SQLAlchemyError:
        db.rollback()
        logger.exception(
            "Error al actualizar sucursal %s",
            branch_id,
        )
        raise HTTPException(
            status_code=503,
            detail="No fue posible actualizar la sucursal",
        ) from None


@router.delete(
    "/{branch_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desactivar sucursal",
    description=(
        "Desactiva una sucursal sin eliminarla físicamente."
    ),
    responses={
        404: {"description": "Sucursal no encontrada"},
    },
)
def deactivate_branch(
    actor: AdminUser,
    db: DbSession,
    branch_id: int = Path(gt=0),
):
    try:
        branch_service.deactivate_branch(
            db=db,
            branch_id=branch_id,
        )

        return Response(
            status_code=status.HTTP_204_NO_CONTENT,
        )

    except SQLAlchemyError:
        db.rollback()
        logger.exception(
            "Error al desactivar sucursal %s",
            branch_id,
        )
        raise HTTPException(
            status_code=503,
            detail="No fue posible desactivar la sucursal",
        ) from None


@router.patch(
    "/{branch_id}/reactivar",
    response_model=BranchResponse,
    summary="Reactivar sucursal",
)
def reactivate_branch(
    actor: AdminUser,
    db: DbSession,
    branch_id: int = Path(gt=0),
):
    try:
        return branch_service.reactivate_branch(
            db=db,
            branch_id=branch_id,
        )

    except SQLAlchemyError:
        db.rollback()
        logger.exception(
            "Error al reactivar sucursal %s",
            branch_id,
        )
        raise HTTPException(
            status_code=503,
            detail="No fue posible reactivar la sucursal",
        ) from None
