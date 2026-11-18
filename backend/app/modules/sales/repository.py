from sqlalchemy import select
from fastapi import HTTPException
from app.modules.sales.model import Sale
from app.modules.orders.model import Order
from app.shared.commerce import authorize, scope_query, dated


def get_sale(db, actor, sale_id, *, lock=False):
    # Uniform lock order: order -> sale -> payment -> inventory.
    order_id = db.scalar(select(Sale.pedido_id).where(Sale.id == sale_id))
    if lock and order_id is not None:
        db.scalar(
            select(Order)
            .where(Order.id == order_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    stmt = select(Sale).where(Sale.id == sale_id)
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    sale = db.scalar(stmt)
    if sale is None:
        raise HTTPException(404, "Venta no encontrada")
    authorize(db, actor, sale)
    return sale


def query_sales(db, actor, dates, branch=None, state=None, employee=None):
    stmt = scope_query(db, actor, select(Sale), Sale, branch)
    stmt = dated(stmt, Sale.fecha, dates)
    if state:
        stmt = stmt.where(Sale.estado == state)
    if employee:
        stmt = stmt.where(Sale.empleado_id == employee)
    return stmt.order_by(Sale.fecha.desc(), Sale.id.desc())
