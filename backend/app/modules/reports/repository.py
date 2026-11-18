"""Agregaciones SQL; no se cargan tablas completas para sumar en Python."""

from sqlalchemy import select, func, cast, String
from app.modules.sales.model import Sale, SaleDetail
from app.modules.payments.model import Payment, PaymentMethod
from app.modules.inventory.model import Inventory, InventoryMovement
from app.shared.commerce import dated


def filtered(stmt, column, dates, branch, column_branch=Sale.sucursal_id):
    stmt = dated(stmt, column, dates)
    if branch is not None:
        stmt = stmt.where(column_branch == branch)
    return stmt


def sales_totals(db, dates, branch, group, tz, limit, offset, order="grupo"):
    if group == "sucursal":
        key = cast(Sale.sucursal_id, String)
    elif group == "empleado":
        key = func.coalesce(cast(Sale.empleado_id, String), "EN_LINEA")
    elif db.bind.dialect.name == "postgresql":
        unit = {"dia": "day", "semana": "week", "mes": "month", "anio": "year"}[group]
        key = cast(func.date_trunc(unit, func.timezone(tz, Sale.fecha)), String)
    else:
        # SQLite tests use UTC only; production PostgreSQL performs timezone conversion.
        formats = {"dia": "%Y-%m-%d", "semana": "%Y-%W", "mes": "%Y-%m", "anio": "%Y"}
        key = func.strftime(formats[group], Sale.fecha)
    stmt = select(
        key.label("grupo"),
        func.count().label("ventas"),
        func.sum(Sale.total).label("total"),
    ).where(Sale.estado == "CONFIRMADA")
    ordering = (
        [key]
        if order == "grupo"
        else [
            func.sum(Sale.total).desc()
            if order == "total_desc"
            else func.sum(Sale.total).asc(),
            key,
        ]
    )
    stmt = (
        filtered(stmt, Sale.fecha, dates, branch)
        .group_by(key)
        .order_by(*ordering)
        .limit(limit)
        .offset(offset)
    )
    return list(db.execute(stmt).mappings())


def top_products(db, dates, branch, limit=20, offset=0, least=False):
    if least:
        from app.modules.products.model import Product

        totals = (
            select(
                SaleDetail.producto_id,
                func.sum(SaleDetail.cantidad).label("cantidad"),
                func.sum(SaleDetail.subtotal).label("total"),
            )
            .join(Sale)
            .where(Sale.estado == "CONFIRMADA")
        )
        totals = (
            filtered(totals, Sale.fecha, dates, branch)
            .group_by(SaleDetail.producto_id)
            .subquery()
        )
        quantity = func.coalesce(totals.c.cantidad, 0)
        stmt = (
            select(
                Product.id.label("producto_id"),
                quantity.label("cantidad"),
                func.coalesce(totals.c.total, 0).label("total"),
            )
            .outerjoin(totals, totals.c.producto_id == Product.id)
            .order_by(quantity, Product.id)
            .limit(limit)
            .offset(offset)
        )
        return list(db.execute(stmt).mappings())
    stmt = (
        select(
            SaleDetail.producto_id,
            func.sum(SaleDetail.cantidad).label("cantidad"),
            func.sum(SaleDetail.subtotal).label("total"),
        )
        .join(Sale)
        .where(Sale.estado == "CONFIRMADA")
    )
    stmt = (
        filtered(stmt, Sale.fecha, dates, branch)
        .group_by(SaleDetail.producto_id)
        .order_by(func.sum(SaleDetail.cantidad).desc(), SaleDetail.producto_id)
        .limit(limit)
        .offset(offset)
    )
    return list(db.execute(stmt).mappings())


def payment_totals(db, dates, branch, confirmed_only, limit, offset):
    stmt = (
        select(
            Payment.estado,
            PaymentMethod.codigo.label("metodo"),
            Sale.sucursal_id,
            func.count().label("pagos"),
            func.sum(Payment.monto).label("total"),
        )
        .join(Sale)
        .join(PaymentMethod, PaymentMethod.id == Payment.metodo_pago_id)
    )
    if confirmed_only:
        stmt = stmt.where(Payment.estado == "APROBADO", Sale.estado == "CONFIRMADA")
    stmt = filtered(
        stmt, Payment.paid_at if confirmed_only else Payment.created_at, dates, branch
    )
    return list(
        db.execute(
            stmt.group_by(Payment.estado, PaymentMethod.codigo, Sale.sucursal_id)
            .order_by(Sale.sucursal_id, Payment.estado, PaymentMethod.codigo)
            .limit(limit)
            .offset(offset)
        ).mappings()
    )


def stock(db, branch, low, limit, offset):
    stmt = select(Inventory).order_by(Inventory.sucursal_id, Inventory.producto_id)
    if branch:
        stmt = stmt.where(Inventory.sucursal_id == branch)
    if low:
        stmt = stmt.where(Inventory.cantidad <= Inventory.stock_minimo)
    return list(db.scalars(stmt.limit(limit).offset(offset)))


def movements(db, dates, branch, kind, limit, offset):
    stmt = select(InventoryMovement).join(Inventory)
    stmt = filtered(
        stmt, InventoryMovement.created_at, dates, branch, Inventory.sucursal_id
    )
    if kind:
        stmt = stmt.where(InventoryMovement.tipo == kind)
    return list(
        db.scalars(
            stmt.order_by(InventoryMovement.id.desc()).limit(limit).offset(offset)
        )
    )
