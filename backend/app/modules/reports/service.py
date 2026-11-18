from datetime import timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select, func
from app.modules.reports import repository
from app.modules.products.model import Product
from app.modules.branches.model import Branch
from app.modules.customers.model import Customer
from app.modules.orders.model import Order
from app.modules.sales.model import Sale
from app.modules.payments.model import Payment
from app.modules.inventory.model import Inventory
from app.shared.commerce import DateFilters, utcnow


def zone(db, name):
    try:
        tz = ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(422, "Zona horaria IANA inválida") from None
    if db.bind.dialect.name != "postgresql" and name != "UTC":
        raise HTTPException(422, "Agrupación por zona horaria requiere PostgreSQL")
    return tz


def dashboard(db, branch, tz_name):
    tz = zone(db, tz_name)
    now = utcnow().astimezone(tz)
    day = now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(
        timezone.utc
    )
    month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).astimezone(
        timezone.utc
    )

    def count(model, *conditions):
        return (
            db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0
        )

    def scoped(model):
        return [model.sucursal_id == branch] if branch else []

    income = (
        select(func.coalesce(func.sum(Payment.monto), 0))
        .join(Sale)
        .where(
            Payment.estado == "APROBADO",
            Sale.estado == "CONFIRMADA",
            Payment.paid_at >= month,
            Payment.paid_at <= utcnow(),
            *scoped(Sale),
        )
    )
    return dict(
        zona_horaria=tz_name,
        productos_activos=count(Product, Product.activo.is_(True)),
        sucursales_activas=count(
            Branch, Branch.activo.is_(True), *([Branch.id == branch] if branch else [])
        ),
        clientes_registrados=count(Customer),
        pedidos_pendientes=count(Order, Order.estado == "PENDIENTE", *scoped(Order)),
        ventas_dia=count(
            Sale,
            Sale.estado == "CONFIRMADA",
            Sale.fecha >= day,
            Sale.fecha <= utcnow(),
            *scoped(Sale),
        ),
        ingresos_mes=Decimal(db.scalar(income)),
        productos_mas_vendidos=repository.top_products(
            db, DateFilters(desde=month, hasta=utcnow()), branch, 10
        ),
        alertas_inventario=count(
            Inventory, Inventory.cantidad <= Inventory.stock_minimo, *scoped(Inventory)
        ),
    )
