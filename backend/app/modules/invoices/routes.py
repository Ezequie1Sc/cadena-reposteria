from typing import Annotated, Literal
from fastapi import APIRouter, Path
from sqlalchemy import select
from app.core.auth import DbSession, CurrentUser
from app.core.permissions import AdminUser, StaffUser
from app.modules.invoices.model import Invoice
from app.modules.sales.model import Sale
from app.modules.invoices.schemas import (
    InvoiceCreate,
    InvoiceTransition,
    InvoiceResponse,
)
from app.modules.invoices.repository import get_invoice
from app.modules.invoices.service import create_invoice, transition_invoice
from app.shared.commerce import (
    Key,
    Limit,
    Offset,
    EventResponse,
    scope_query,
    page,
    history,
)

router = APIRouter(prefix="/facturas", tags=["Solicitudes de factura"])
ID = Annotated[int, Path(gt=0)]


@router.post("", response_model=InvoiceResponse, status_code=201)
def create(
    data: InvoiceCreate, db: DbSession, actor: CurrentUser, idempotency_key: Key
):
    return create_invoice(db, actor, data, idempotency_key)


@router.get("", response_model=list[InvoiceResponse])
def listing(
    db: DbSession,
    actor: CurrentUser,
    estado: Literal["PENDIENTE", "EMITIDA", "CANCELADA"] | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
):
    stmt = scope_query(
        db, actor, select(Invoice).join(Sale, Sale.id == Invoice.venta_id), Sale
    ).order_by(Invoice.id.desc())
    if estado:
        stmt = stmt.where(Invoice.estado == estado)
    return page(db, stmt, limit, offset)[1]


@router.get("/{invoice_id}", response_model=InvoiceResponse)
def detail(invoice_id: ID, db: DbSession, actor: CurrentUser):
    return get_invoice(db, actor, invoice_id)[0]


@router.patch("/{invoice_id}/estado", response_model=InvoiceResponse)
def transition(
    invoice_id: ID, data: InvoiceTransition, db: DbSession, actor: AdminUser
):
    return transition_invoice(db, actor, invoice_id, data)


@router.get("/{invoice_id}/historial", response_model=list[EventResponse])
def events(
    invoice_id: ID,
    db: DbSession,
    actor: StaffUser,
    limit: Limit = 100,
    offset: Offset = 0,
):
    get_invoice(db, actor, invoice_id)
    return history(db, "FACTURA", invoice_id, limit, offset)
