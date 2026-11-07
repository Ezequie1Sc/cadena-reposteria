
"""Endpoints protegidos para la gestión de pedidos."""

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status
from sqlalchemy.exc import SQLAlchemyError

from app.core.auth import DbSession
from app.core.permissions import StaffUser
from app.modules.orders.schemas import (
    OrderCreate,
    OrderListResponse,
    OrderResponse,
    OrderStatus,
    OrderStatusUpdate,
)
from app.modules.orders.service import order_service


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/pedidos",
    tags=["Pedidos"],
)

OrderID = Annotated[int, Path(gt=0)]


@router.get(
    "",
    response_model=OrderListResponse,
    summary="Listar pedidos",
)
def list_orders(
    db: DbSession,
    staff: StaffUser,
    cliente_id: Annotated[int | None, Query(gt=0)] = None,
    sucursal_id: Annotated[int | None, Query(gt=0)] = None,
    estado: OrderStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> OrderListResponse:
    """Lista pedidos con filtros y paginación."""

    try:
        return order_service.get_all(
            db=db,
            cliente_id=cliente_id,
            sucursal_id=sucursal_id,
            estado=estado,
            limit=limit,
            offset=offset,
        )

    except SQLAlchemyError:
        db.rollback()

        logger.exception(
            "Error al consultar pedidos"
        )

        raise HTTPException(
            status_code=503,
            detail="No fue posible consultar los pedidos",
        ) from None


@router.get(
    "/numero/{numero_pedido}",
    response_model=OrderResponse,
    summary="Consultar pedido por número",
)
def get_order_by_number(
    numero_pedido: Annotated[
        str,
        Path(min_length=1, max_length=40),
    ],
    db: DbSession,
    staff: StaffUser,
) -> OrderResponse:
    """Consulta un pedido por su número único."""

    try:
        return order_service.get_by_number(
            db,
            numero_pedido,
        )

    except SQLAlchemyError:
        db.rollback()

        logger.exception(
            "Error al consultar pedido por número"
        )

        raise HTTPException(
            status_code=503,
            detail="No fue posible consultar el pedido",
        ) from None


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    summary="Consultar pedido",
)
def get_order(
    order_id: OrderID,
    db: DbSession,
    staff: StaffUser,
) -> OrderResponse:
    """Consulta un pedido y sus productos."""

    try:
        return order_service.get_by_id(
            db,
            order_id,
        )

    except SQLAlchemyError:
        db.rollback()

        logger.exception(
            "Error al consultar pedido %s",
            order_id,
        )

        raise HTTPException(
            status_code=503,
            detail="No fue posible consultar el pedido",
        ) from None


@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear pedido",
)
def create_order(
    data: OrderCreate,
    db: DbSession,
    staff: StaffUser,
) -> OrderResponse:
    """Crea un pedido y reserva existencias."""

    try:
        return order_service.create(
            db,
            data,
            usuario_id=staff.id,
        )

    except SQLAlchemyError:
        db.rollback()

        logger.exception(
            "Error al crear pedido"
        )

        raise HTTPException(
            status_code=503,
            detail="No fue posible crear el pedido",
        ) from None


@router.patch(
    "/{order_id}/estado",
    response_model=OrderResponse,
    summary="Actualizar estado de pedido",
)
def update_order_status(
    order_id: OrderID,
    data: OrderStatusUpdate,
    db: DbSession,
    staff: StaffUser,
) -> OrderResponse:
    """Actualiza el estado y repone stock al cancelar."""

    try:
        return order_service.update_status(
            db,
            order_id,
            data,
            usuario_id=staff.id,
        )

    except SQLAlchemyError:
        db.rollback()

        logger.exception(
            "Error al actualizar pedido %s",
            order_id,
        )

        raise HTTPException(
            status_code=503,
            detail="No fue posible actualizar el pedido",
        ) from None
