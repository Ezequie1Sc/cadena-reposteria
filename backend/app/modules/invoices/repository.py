from fastapi import HTTPException
from sqlalchemy import select
from app.modules.invoices.model import Invoice
from app.modules.sales.repository import get_sale


def get_invoice(db, actor, invoice_id, lock=False):
    sale_id = db.scalar(select(Invoice.venta_id).where(Invoice.id == invoice_id))
    if sale_id is None:
        raise HTTPException(404, "Solicitud no encontrada")
    sale = get_sale(db, actor, sale_id, lock=lock)
    stmt = select(Invoice).where(Invoice.id == invoice_id)
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    return db.scalar(stmt), sale
