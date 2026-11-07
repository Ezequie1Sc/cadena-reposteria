
"""Endpoints protegidos para la gestión de inventarios."""

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status
from sqlalchemy.exc import SQLAlchemyError

from app.core.auth import DbSession
from app.core.permissions import AdminUser, StaffUser
from app.modules.inventory.schemas import (
    InventoryAdjustmentCreate,
    InventoryCreate,
    InventoryListResponse,
    InventoryMovementCreate,
    InventoryMovementListResponse,
    InventoryResponse,
    InventoryTransferCreate,
    InventoryTransferResponse,
    InventoryUpdate,
)
from app.modules.inventory.service import inventory_service


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/inventarios",
    tags=["Inventarios"],
)

InventoryID = Annotated[int, Path(gt=0)]


@router.get(
    "",
    response_model=InventoryListResponse,
    summary="Listar inventarios",
)
def list_inventories(
    db: DbSession,
    staff: StaffUser,
    sucursal_id: Annotated[int | None, Query(gt=0)] = None,
    producto_id: Annotated[int | None, Query(gt=0)] = None,
    solo_bajo_stock: bool = False,
) -> InventoryListResponse:
    try:
        return inventory_service.get_all(
            db=db,
            sucursal_id=sucursal_id,
            producto_id=producto_id,
            solo_bajo_stock=solo_bajo_stock,
        )
    except SQLAlchemyError:
        logger.exception("Error al consultar inventarios")
        raise HTTPException(
            status_code=503,
            detail="No fue posible consultar inventarios",
        ) from None


@router.get(
    "/{inventory_id}",
    response_model=InventoryResponse,
    summary="Consultar inventario",
)
def get_inventory(
    inventory_id: InventoryID,
    db: DbSession,
    staff: StaffUser,
) -> InventoryResponse:
    try:
        return inventory_service.get_by_id(db, inventory_id)
    except SQLAlchemyError:
        logger.exception("Error al consultar inventario")
        raise HTTPException(
            status_code=503,
            detail="No fue posible consultar el inventario",
        ) from None


@router.post(
    "",
    response_model=InventoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear inventario de producto por sucursal",
)
def create_inventory(
    data: InventoryCreate,
    db: DbSession,
    admin: AdminUser,
) -> InventoryResponse:
    try:
        return inventory_service.create(db, data)
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Error al crear inventario")
        raise HTTPException(
            status_code=503,
            detail="No fue posible crear el inventario",
        ) from None


@router.patch(
    "/{inventory_id}",
    response_model=InventoryResponse,
    summary="Configurar stock mínimo",
)
def update_inventory(
    inventory_id: InventoryID,
    data: InventoryUpdate,
    db: DbSession,
    admin: AdminUser,
) -> InventoryResponse:
    try:
        return inventory_service.update_minimum_stock(
            db,
            inventory_id,
            data,
        )
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Error al actualizar inventario")
        raise HTTPException(
            status_code=503,
            detail="No fue posible actualizar el inventario",
        ) from None


@router.post(
    "/{inventory_id}/entradas",
    response_model=InventoryResponse,
    summary="Registrar entrada de productos",
)
def register_entry(
    inventory_id: InventoryID,
    data: InventoryMovementCreate,
    db: DbSession,
    staff: StaffUser,
) -> InventoryResponse:
    try:
        return inventory_service.register_entry(
            db,
            inventory_id,
            data,
            usuario_id=staff.id,
        )
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Error al registrar entrada")
        raise HTTPException(
            status_code=503,
            detail="No fue posible registrar la entrada",
        ) from None


@router.post(
    "/{inventory_id}/salidas",
    response_model=InventoryResponse,
    summary="Registrar salida de productos",
)
def register_exit(
    inventory_id: InventoryID,
    data: InventoryMovementCreate,
    db: DbSession,
    staff: StaffUser,
) -> InventoryResponse:
    try:
        return inventory_service.register_exit(
            db,
            inventory_id,
            data,
            usuario_id=staff.id,
        )
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Error al registrar salida")
        raise HTTPException(
            status_code=503,
            detail="No fue posible registrar la salida",
        ) from None


@router.post(
    "/{inventory_id}/ajustes",
    response_model=InventoryResponse,
    summary="Ajustar existencias",
)
def adjust_inventory(
    inventory_id: InventoryID,
    data: InventoryAdjustmentCreate,
    db: DbSession,
    admin: AdminUser,
) -> InventoryResponse:
    try:
        return inventory_service.adjust_stock(
            db,
            inventory_id,
            data,
            usuario_id=admin.id,
        )
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Error al ajustar inventario")
        raise HTTPException(
            status_code=503,
            detail="No fue posible ajustar el inventario",
        ) from None


@router.post(
    "/{inventory_id}/traspasos",
    response_model=InventoryTransferResponse,
    summary="Traspasar productos entre sucursales",
)
def transfer_inventory(
    inventory_id: InventoryID,
    data: InventoryTransferCreate,
    db: DbSession,
    admin: AdminUser,
) -> InventoryTransferResponse:
    try:
        return inventory_service.transfer(
            db,
            inventory_id,
            data,
            usuario_id=admin.id,
        )
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Error al traspasar inventario")
        raise HTTPException(
            status_code=503,
            detail="No fue posible realizar el traspaso",
        ) from None


@router.get(
    "/{inventory_id}/movimientos",
    response_model=InventoryMovementListResponse,
    summary="Consultar movimientos de inventario",
)
def list_movements(
    inventory_id: InventoryID,
    db: DbSession,
    staff: StaffUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> InventoryMovementListResponse:
    try:
        return inventory_service.get_movements(
            db,
            inventory_id,
            limit=limit,
            offset=offset,
        )
    except SQLAlchemyError:
        logger.exception("Error al consultar movimientos")
        raise HTTPException(
            status_code=503,
            detail="No fue posible consultar movimientos",
        ) from None
