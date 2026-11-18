from sqlalchemy import select
from fastapi import HTTPException
from app.modules.payments.model import Payment, PaymentMethod
from app.modules.sales.model import Sale
from app.modules.sales.repository import get_sale
from app.shared.commerce import scope_query, dated


def get_payment(db, actor, payment_id, lock=False):
    sale_id = db.scalar(select(Payment.venta_id).where(Payment.id == payment_id))
    if sale_id is None:
        raise HTTPException(404, "Pago no encontrado")
    sale = get_sale(db, actor, sale_id, lock=lock)
    stmt = select(Payment).where(Payment.id == payment_id)
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    return db.scalar(stmt), sale


def query_payments(db, actor, dates, branch=None, state=None, method=None):
    stmt = scope_query(
        db, actor, select(Payment).join(Sale, Sale.id == Payment.venta_id), Sale, branch
    )
    stmt = dated(stmt, Payment.created_at, dates)
    if state:
        stmt = stmt.where(Payment.estado == state)
    if method:
        stmt = stmt.join(PaymentMethod).where(PaymentMethod.codigo == method)
    return stmt.order_by(Payment.id.desc())
