from typing import Annotated
from fastapi import APIRouter, Path
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from app.core.auth import DbSession, CurrentUser
from app.modules.sales.model import Sale
from app.modules.tickets.model import Ticket
from app.modules.tickets.schemas import TicketResponse
from app.modules.tickets.service import generate, retrieve, printable, present
from app.shared.commerce import Limit, Offset, scope_query, page

router = APIRouter(prefix="/tickets", tags=["Tickets"])
ID = Annotated[int, Path(gt=0)]


@router.post("/venta/{sale_id}", response_model=TicketResponse)
def create(sale_id: ID, db: DbSession, actor: CurrentUser):
    return generate(db, actor, sale_id)


@router.get("", response_model=list[TicketResponse])
def listing(db: DbSession, actor: CurrentUser, limit: Limit = 20, offset: Offset = 0):
    stmt = scope_query(
        db, actor, select(Ticket).join(Sale, Sale.id == Ticket.venta_id), Sale
    ).order_by(Ticket.id.desc())
    return [
        present(db, t, db.get(Sale, t.venta_id))
        for t in page(db, stmt, limit, offset)[1]
    ]


@router.get("/{ticket_id}", response_model=TicketResponse)
def detail(ticket_id: ID, db: DbSession, actor: CurrentUser):
    return retrieve(db, actor, ticket_id)


@router.get("/{ticket_id}/imprimir", response_class=HTMLResponse)
def download(ticket_id: ID, db: DbSession, actor: CurrentUser):
    ticket = retrieve(db, actor, ticket_id)
    return HTMLResponse(
        printable(ticket),
        headers={
            "Content-Disposition": f'inline; filename="{ticket.numero_ticket}.html"',
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
