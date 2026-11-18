from typing import Annotated
from datetime import datetime
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Path
from pydantic import Field, field_validator
from app.core.auth import DbSession
from app.core.permissions import require_roles, RoleID
from app.modules.users.model import User
from app.modules.orders.schemas import (
    OrderCreate,
    OrderItemCreate,
    OrderResponse,
    OrderListResponse,
    OrderStatusUpdate,
)
from app.modules.orders.commercial_service import create_order, update_order
from app.modules.orders.service import order_service
from app.shared.commerce import StrictModel, Key, Limit, Offset, own_customer, authorize

router = APIRouter(prefix="/mis-pedidos", tags=["Pedidos del cliente"])
ClientUser = Annotated[User, Depends(require_roles(RoleID.CLIENTE))]
ID = Annotated[int, Path(gt=0)]


class CustomerOrderCreate(StrictModel):
    sucursal_id: int = Field(gt=0)
    productos: list[OrderItemCreate] = Field(min_length=1, max_length=100)
    direccion_entrega: str | None = Field(default=None, max_length=1000)
    notas: str | None = Field(default=None, max_length=2000)
    _unique = field_validator("productos")(
        OrderCreate.validate_unique_products.__func__
    )


@router.post("", response_model=OrderResponse, status_code=201)
def create(
    data: CustomerOrderCreate, db: DbSession, actor: ClientUser, idempotency_key: Key
):
    customer = own_customer(db, actor)
    return create_order(
        db,
        actor,
        OrderCreate(cliente_id=customer.id, **data.model_dump()),
        idempotency_key,
    )


@router.get("", response_model=OrderListResponse)
def listing(db: DbSession, actor: ClientUser, limit: Limit = 20, offset: Offset = 0):
    return order_service.get_all(
        db, cliente_id=own_customer(db, actor).id, limit=limit, offset=offset
    )


@router.get("/{order_id}", response_model=OrderResponse)
def detail(order_id: ID, db: DbSession, actor: ClientUser):
    order = order_service._require_order(db, order_id)
    authorize(db, actor, order)
    return OrderResponse.model_validate(order)


@router.post("/{order_id}/cancelar", response_model=OrderResponse)
def cancel(order_id: ID, db: DbSession, actor: ClientUser):
    return update_order(
        db,
        actor,
        order_id,
        OrderStatusUpdate(estado="CANCELADO"),
        "Cancelación solicitada por cliente",
    )


class CustomerOrderEvent(BaseModel):
    anterior: str | None
    estado: str
    fecha: datetime


@router.get("/{order_id}/historial", response_model=list[CustomerOrderEvent])
def events(
    order_id: ID,
    db: DbSession,
    actor: ClientUser,
    limit: Limit = 100,
    offset: Offset = 0,
):
    from app.shared.commerce import history

    order = order_service._require_order(db, order_id)
    authorize(db, actor, order)
    return [
        {"anterior": e.anterior, "estado": e.estado, "fecha": e.created_at}
        for e in history(db, "PEDIDO", order_id, limit, offset)
    ]
