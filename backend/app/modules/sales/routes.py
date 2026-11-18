from app.shared.commerce import Dates
from typing import Annotated, Literal
from fastapi import APIRouter, Path, Query
from app.core.auth import DbSession, CurrentUser
from app.core.permissions import StaffUser, AdminUser
from app.shared.commerce import (
    Key,
    Limit,
    Offset,
    CancelRequest,
    EventResponse,
    page,
    history,
)
from app.modules.sales.schemas import (
    SaleCreate,
    SaleResponse,
    SaleList,
    ExpirationResponse,
)
from app.modules.sales.repository import get_sale, query_sales
from app.modules.sales.service import create_sale, cancel_sale, expire_sales

router = APIRouter(prefix="/ventas", tags=["Ventas"])
ID = Annotated[int, Path(gt=0)]


@router.post("", response_model=SaleResponse, status_code=201)
def create(data: SaleCreate, db: DbSession, actor: StaffUser, idempotency_key: Key):
    return create_sale(db, actor, data, idempotency_key)


@router.get("", response_model=SaleList)
def listing(
    db: DbSession,
    actor: CurrentUser,
    dates: Dates,
    sucursal_id: Annotated[int | None, Query(gt=0)] = None,
    estado: Literal["PENDIENTE", "CONFIRMADA", "CANCELADA"] | None = None,
    empleado_id: Annotated[int | None, Query(gt=0)] = None,
    limit: Limit = 20,
    offset: Offset = 0,
):
    count, items = page(
        db,
        query_sales(db, actor, dates, sucursal_id, estado, empleado_id),
        limit,
        offset,
    )
    return {"total": count, "ventas": items}


@router.post("/expirar", response_model=ExpirationResponse)
def expire(db: DbSession, actor: AdminUser, limit: Limit = 100):
    return expire_sales(db, actor, limit)


@router.get("/{sale_id}", response_model=SaleResponse)
def detail(sale_id: ID, db: DbSession, actor: CurrentUser):
    return get_sale(db, actor, sale_id)


@router.post("/{sale_id}/cancelar", response_model=SaleResponse)
def cancel(sale_id: ID, data: CancelRequest, db: DbSession, actor: StaffUser):
    return cancel_sale(db, actor, sale_id, data)


@router.get("/{sale_id}/historial", response_model=list[EventResponse])
def events(
    sale_id: ID, db: DbSession, actor: StaffUser, limit: Limit = 100, offset: Offset = 0
):
    get_sale(db, actor, sale_id)
    return history(db, "VENTA", sale_id, limit, offset)
