from fastapi import HTTPException
from sqlalchemy import select
from app.modules.tickets.model import Ticket
from app.modules.sales.repository import get_sale


def get_ticket(db, actor, ticket_id):
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(404, "Ticket no encontrado")
    return ticket, get_sale(db, actor, ticket.venta_id)


def for_sale(db, sale_id):
    return db.scalar(select(Ticket).where(Ticket.venta_id == sale_id))
