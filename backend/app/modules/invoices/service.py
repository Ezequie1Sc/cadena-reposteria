from app.core.roles import RoleID
from fastapi import HTTPException
from sqlalchemy import select
from app.modules.invoices.model import Invoice
from app.modules.invoices.schemas import InvoiceResponse
from app.modules.invoices.repository import get_invoice
from app.modules.sales.repository import get_sale
from app.modules.customers.model import Customer
from app.modules.payments.model import Payment
from app.shared.commerce import (
    atomic,
    record,
    begin_idempotency,
    finish_idempotency,
    utcnow,
)


@atomic
def create_invoice(db, actor, data, key):
    prior, digest = begin_idempotency(
        db, actor, "factura", key, data.model_dump(mode="json")
    )
    if prior:
        return InvoiceResponse.model_validate(get_invoice(db, actor, prior)[0])
    sale = get_sale(db, actor, data.venta_id, lock=True)
    if sale.estado != "CONFIRMADA" or not db.scalar(
        select(Payment.id).where(
            Payment.venta_id == sale.id, Payment.estado == "APROBADO"
        )
    ):
        raise HTTPException(409, "Se requiere venta pagada")
    if sale.cliente_id is not None and sale.cliente_id != data.cliente_id:
        raise HTTPException(403, "Cliente distinto al de la venta")
    if sale.cliente_id is None and actor.rol_id != RoleID.ADMINISTRADOR:
        raise HTTPException(
            403, "Administrador debe asociar al cliente para facturar venta anónima"
        )
    customer = db.get(Customer, data.cliente_id)
    if customer is None or not customer.activo:
        raise HTTPException(409, "Cliente no disponible")
    if db.scalar(select(Invoice.id).where(Invoice.venta_id == sale.id)):
        raise HTTPException(409, "Ya existe una solicitud de esta venta")
    if sale.cliente_id is None:
        sale.cliente_id = data.cliente_id
        record(
            db,
            "VENTA",
            sale,
            actor,
            sale.estado,
            "Cliente vinculado por administrador para solicitud fiscal",
        )
    invoice = Invoice(**data.model_dump())
    db.add(invoice)
    db.flush()
    record(db, "FACTURA", invoice, actor)
    finish_idempotency(db, actor, "factura", key, digest, invoice.id)
    return InvoiceResponse.model_validate(invoice)


@atomic
def transition_invoice(db, actor, invoice_id, data):
    if actor.rol_id != RoleID.ADMINISTRADOR:
        raise HTTPException(403, "Sólo administrador")
    invoice, sale = get_invoice(db, actor, invoice_id, lock=True)
    if invoice.estado == "CANCELADA" or invoice.estado == data.estado:
        raise HTTPException(409, "Transición no permitida")
    if data.estado == "EMITIDA":
        if sale.estado != "CONFIRMADA":
            raise HTTPException(409, "Venta no confirmada")
        if data.fecha_emision > utcnow():
            raise HTTPException(422, "Fecha de emisión futura")
        invoice.uuid = data.uuid
        invoice.proveedor = data.proveedor
        invoice.referencia_proveedor = data.referencia_proveedor
        invoice.fecha_emision = data.fecha_emision
    elif invoice.estado == "EMITIDA" and not data.referencia_proveedor:
        raise HTTPException(422, "Se requiere referencia de cancelación fiscal externa")
    old = invoice.estado
    invoice.estado = data.estado
    record(
        db,
        "FACTURA",
        invoice,
        actor,
        old,
        data.motivo
        + (" | " + data.referencia_proveedor if data.referencia_proveedor else ""),
    )
    return InvoiceResponse.model_validate(invoice)
