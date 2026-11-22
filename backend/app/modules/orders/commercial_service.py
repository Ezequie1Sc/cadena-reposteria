"""Coordinación de los pedidos existentes con venta, pago e historial."""

from app.core.roles import RoleID
from fastapi import HTTPException
from sqlalchemy import select
from app.modules.orders.service import order_service as legacy
from app.modules.orders.model import Order
from app.modules.orders.schemas import OrderResponse, OrderStatus
from app.modules.users.model import User
from app.modules.sales.model import Sale
from app.modules.sales.service import sale_for_order, cancel_locked
from app.modules.payments.model import Payment
from app.shared.commerce import (
    atomic,
    authorize,
    begin_idempotency,
    finish_idempotency,
    record,
    CancelRequest,
)


@atomic
def create_order(db, actor, data, key=None):
    if key:
        prior, digest = begin_idempotency(
            db, actor, "pedido", key, data.model_dump(mode="json")
        )
        if prior:
            order = db.get(Order, prior)
            authorize(db, actor, order)
            return OrderResponse.model_validate(order)
    from app.modules.branches.model import Branch
    from app.modules.customers.model import Customer
    from app.modules.products.model import Product
    from app.core.permissions import scope_branch
    from app.shared.commerce import own_customer

    if actor.rol_id == RoleID.CLIENTE:
        if own_customer(db, actor).id != data.cliente_id:
            raise HTTPException(403, "Cliente no autorizado")
    else:
        scope_branch(db, actor, data.sucursal_id)
    # Keep active catalog/profile state stable throughout the reservation transaction.
    db.scalar(
        select(Branch).where(Branch.id == data.sucursal_id).with_for_update(read=True)
    )
    db.scalar(
        select(Customer)
        .where(Customer.id == data.cliente_id)
        .with_for_update(read=True)
    )
    for item in sorted(data.productos, key=lambda item: item.producto_id):
        db.scalar(
            select(Product)
            .where(Product.id == item.producto_id)
            .with_for_update(read=True)
        )
    result = legacy.create(db, data, usuario_id=actor.id, commit=False)
    order = db.get(Order, result.id)
    from app.shared.commerce import money

    if money(order.total) <= 0:
        raise HTTPException(409, "El pedido debe tener importe positivo")
    sale_for_order(db, actor, order)
    record(db, "PEDIDO", order, actor)
    if key:
        finish_idempotency(db, actor, "pedido", key, digest, order.id)
    return OrderResponse.model_validate(order)


@atomic
def update_order(db, actor, order_id, data, reason="Cambio de estado de pedido"):
    order = db.scalar(
        select(Order)
        .where(Order.id == order_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if order is None:
        raise HTTPException(404, "Pedido no encontrado")
    authorize(db, actor, order)
    if data.estado == order.estado:
        raise HTTPException(409, "El pedido ya tiene ese estado")
    if actor.rol_id == RoleID.CLIENTE and (
        data.estado != OrderStatus.CANCELADO or order.estado != "PENDIENTE"
    ):
        raise HTTPException(403, "El cliente sólo puede cancelar un pedido pendiente")
    sale = db.scalar(
        select(Sale)
        .where(Sale.pedido_id == order.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if data.estado == OrderStatus.CANCELADO and sale:
        cancel_locked(db, actor, sale, CancelRequest(motivo=reason))
        return OrderResponse.model_validate(order)
    if data.estado != OrderStatus.CANCELADO:
        approved = (
            sale
            and sale.estado == "CONFIRMADA"
            and db.scalar(
                select(Payment.id).where(
                    Payment.venta_id == sale.id, Payment.estado == "APROBADO"
                )
            )
        )
        if not approved:
            raise HTTPException(
                409, "Se requiere pago completo verificado antes de preparar o entregar"
            )
    old = order.estado
    result = legacy.update_status(db, order_id, data, usuario_id=actor.id, commit=False)
    record(db, "PEDIDO", db.get(Order, order_id), actor, old, reason)
    return result


class CommercialOrderService:
    get_all = staticmethod(legacy.get_all)
    get_by_id = staticmethod(legacy.get_by_id)
    get_by_number = staticmethod(legacy.get_by_number)

    def create(self, db, data, *, usuario_id=None, key=None):
        return create_order(db, db.get(User, usuario_id), data, key)

    def update_status(self, db, order_id, data, *, usuario_id=None):
        return update_order(db, db.get(User, usuario_id), order_id, data)


order_service = CommercialOrderService()
