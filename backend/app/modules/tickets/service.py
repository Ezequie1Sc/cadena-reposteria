from html import escape
from uuid import uuid4
from sqlalchemy import select
from app.modules.tickets.model import Ticket
from app.modules.tickets.repository import get_ticket, for_sale
from app.modules.tickets.schemas import TicketResponse
from app.modules.sales.repository import get_sale
from app.modules.payments.model import Payment, PaymentMethod
from app.modules.branches.model import Branch
from app.shared.commerce import atomic


def present(db, ticket, sale):
    payments = list(
        db.scalars(
            select(Payment).where(Payment.venta_id == sale.id).order_by(Payment.id)
        )
    )
    return TicketResponse(
        id=ticket.id,
        numero_ticket=ticket.numero_ticket,
        fecha_emision=ticket.fecha_emision,
        venta=sale,
        metodos={
            m.id: m.nombre
            for m in db.scalars(
                select(PaymentMethod).where(
                    PaymentMethod.id.in_([p.metodo_pago_id for p in payments])
                )
            )
        },
        sucursal_nombre=db.get(Branch, sale.sucursal_id).nombre,
        pagos=payments,
        pagado=sale.estado == "CONFIRMADA"
        and any(p.estado == "APROBADO" for p in payments),
    )


@atomic
def generate(db, actor, sale_id):
    sale = get_sale(db, actor, sale_id, lock=True)
    ticket = for_sale(db, sale_id)
    if ticket is None:
        ticket = Ticket(venta_id=sale_id, numero_ticket="TIC-" + uuid4().hex.upper())
        db.add(ticket)
        db.flush()
    return present(db, ticket, sale)


def retrieve(db, actor, ticket_id):
    ticket, sale = get_ticket(db, actor, ticket_id)
    return present(db, ticket, sale)


def printable(ticket):
    rows = "".join(
        f"<tr><td>{escape(d.producto_nombre or 'Producto ' + str(d.producto_id))}</td><td>{d.cantidad}</td><td>{d.precio_unitario:.2f}</td><td>{d.subtotal:.2f}</td></tr>"
        for d in ticket.venta.detalles
    )
    payments = "".join(
        f"<li>{escape(ticket.metodos.get(p.metodo_pago_id, str(p.metodo_pago_id)))}: {escape(p.estado)} — {p.monto:.2f} MXN — Referencia: {escape(p.referencia or 'Sin referencia')}</li>"
        for p in ticket.pagos
    )
    return f"""<!doctype html><html lang="es"><meta charset="utf-8"><title>{escape(ticket.numero_ticket)}</title>
    <style>body{{font:16px sans-serif;max-width:760px;margin:2rem auto}}table{{width:100%;border-collapse:collapse}}td,th{{padding:8px;border-bottom:1px solid #ddd}}@media print{{body{{margin:0}}}}</style>
    <h1>Ticket {escape(ticket.numero_ticket)}</h1><p>{escape(ticket.sucursal_nombre)} · {ticket.fecha_emision.isoformat()}</p>
    <p>Venta {ticket.venta.id} · Pedido {ticket.venta.pedido_id or "No aplica"} · Estado {ticket.venta.estado}</p>
    <h2>{"PAGADO" if ticket.pagado else "NO PAGADO / CANCELADO"}</h2>
    <table><tr><th>Producto</th><th>Cantidad</th><th>Precio MXN</th><th>Importe MXN</th></tr>{rows}</table>
    <p>Subtotal: {ticket.venta.subtotal:.2f} · Descuento: {ticket.venta.descuento:.2f} · Total: {ticket.venta.total:.2f} MXN</p>
    <ul>{payments}</ul><p>{ticket.aviso}</p></html>"""
