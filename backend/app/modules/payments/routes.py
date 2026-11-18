from app.shared.commerce import Dates
from typing import Annotated, Literal
from fastapi import APIRouter, Query, Path
from sqlalchemy import select
from app.core.auth import DbSession, CurrentUser
from app.core.permissions import StaffUser
from app.shared.commerce import (
    Key,
    Limit,
    Offset,
    EventResponse,
    page,
    history,
)
from app.modules.payments.schemas import (
    PaymentCreate,
    PaymentTransition,
    PaymentResponse,
    PaymentList,
    MethodResponse,
)
from app.modules.payments.model import PaymentMethod
from app.modules.payments.repository import get_payment, query_payments
from app.modules.payments.service import create_payment, transition_payment

router = APIRouter(prefix="/pagos", tags=["Pagos manuales"])
ID = Annotated[int, Path(gt=0)]


@router.get("/metodos", response_model=list[MethodResponse])
def methods(db: DbSession, actor: CurrentUser):
    return list(
        db.scalars(
            select(PaymentMethod)
            .where(
                PaymentMethod.activo.is_(True),
                PaymentMethod.codigo.in_(["EFECTIVO", "SPEI", "DEPOSITO", "TARJETA"]),
            )
            .order_by(PaymentMethod.id)
        )
    )


@router.post("", response_model=PaymentResponse, status_code=201)
def create(
    data: PaymentCreate, db: DbSession, actor: CurrentUser, idempotency_key: Key
):
    return create_payment(db, actor, data, idempotency_key)


@router.get("", response_model=PaymentList)
def listing(
    db: DbSession,
    actor: CurrentUser,
    dates: Dates,
    sucursal_id: Annotated[int | None, Query(gt=0)] = None,
    estado: Literal[
        "PENDIENTE",
        "APROBADO",
        "RECHAZADO",
        "CANCELADO",
        "REEMBOLSADO",
        "EN_PROCESO",
        "VENCIDO",
    ]
    | None = None,
    metodo: Literal["EFECTIVO", "SPEI", "DEPOSITO", "TARJETA"] | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
):
    count, items = page(
        db, query_payments(db, actor, dates, sucursal_id, estado, metodo), limit, offset
    )
    return {"total": count, "pagos": items}


@router.get("/{payment_id}", response_model=PaymentResponse)
def detail(payment_id: ID, db: DbSession, actor: CurrentUser):
    return get_payment(db, actor, payment_id)[0]


@router.patch("/{payment_id}/estado", response_model=PaymentResponse)
def transition(
    payment_id: ID, data: PaymentTransition, db: DbSession, actor: StaffUser
):
    return transition_payment(db, actor, payment_id, data)


@router.get("/{payment_id}/historial", response_model=list[EventResponse])
def events(
    payment_id: ID,
    db: DbSession,
    actor: StaffUser,
    limit: Limit = 100,
    offset: Offset = 0,
):
    get_payment(db, actor, payment_id)
    return history(db, "PAGO", payment_id, limit, offset)
