from datetime import timedelta
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select
from app.core.permissions import scope_branch, RoleID
from app.modules.branches.model import Branch
from app.modules.customers.model import Customer
from app.modules.employees.model import Employee
from app.modules.users.model import User
from app.modules.products.model import Product
from app.modules.orders.model import Order
from app.modules.sales.model import Sale, SaleDetail
from app.modules.sales.repository import get_sale
from app.modules.payments.model import Payment
from app.modules.invoices.model import Invoice
from app.modules.inventory.commercial import price_lines, move_stock
from app.shared.commerce import (
    atomic,
    money,
    utcnow,
    expired,
    record,
    begin_idempotency,
    finish_idempotency,
)


def response(sale):
    from app.modules.sales.schemas import SaleResponse

    return SaleResponse.model_validate(sale)


@atomic
def create_sale(db, actor, data, key):
    scope_branch(db, actor, data.sucursal_id)
    prior, digest = begin_idempotency(
        db, actor, "venta", key, data.model_dump(mode="json")
    )
    if prior:
        return response(get_sale(db, actor, prior))
    branch = db.scalar(
        select(Branch).where(Branch.id == data.sucursal_id).with_for_update(read=True)
    )
    if branch is None:
        raise HTTPException(404, "Sucursal no encontrada")
    if not branch.activo:
        raise HTTPException(409, "Sucursal inactiva")
    stmt = (
        select(Employee)
        .join(User, User.id == Employee.usuario_id)
        .where(
            Employee.sucursal_id == data.sucursal_id,
            Employee.activo.is_(True),
            User.activo.is_(True),
            User.rol_id == RoleID.EMPLEADO,
        )
    )
    if actor.rol_id == RoleID.EMPLEADO:
        stmt = stmt.where(Employee.usuario_id == actor.id)
    elif data.empleado_id is not None:
        stmt = stmt.where(Employee.id == data.empleado_id)
    else:
        raise HTTPException(422, "El administrador debe indicar empleado_id")
    employee = db.scalar(stmt.with_for_update(read=True))
    if employee is None:
        raise HTTPException(403, "Empleado activo de la sucursal requerido")
    if data.empleado_id is not None and data.empleado_id != employee.id:
        raise HTTPException(403, "No puedes atribuir la venta a otro empleado")
    if data.cliente_id is not None:
        customer = db.scalar(
            select(Customer)
            .where(Customer.id == data.cliente_id)
            .with_for_update(read=True)
        )
        if customer is None:
            raise HTTPException(404, "Cliente no encontrado")
        if not customer.activo:
            raise HTTPException(409, "Cliente inactivo")
    lines = price_lines(db, sorted(data.productos, key=lambda x: x.producto_id))
    total = money(sum(x["subtotal"] for x in lines))
    if total <= 0:
        raise HTTPException(409, "La venta debe tener importe positivo")
    sale = Sale(
        numero_venta="VEN-" + uuid4().hex,
        cliente_id=data.cliente_id,
        empleado_id=employee.id,
        sucursal_id=data.sucursal_id,
        tipo="FISICA",
        subtotal=total,
        total=total,
        descuento=0,
        vence_at=utcnow() + timedelta(minutes=30),
    )
    db.add(sale)
    db.flush()
    sale.detalles = [SaleDetail(**line) for line in lines]
    db.flush()
    move_stock(
        db,
        sale.sucursal_id,
        sale.detalles,
        restore=False,
        resource="VENTA",
        resource_id=sale.id,
        actor_id=actor.id,
    )
    record(db, "VENTA", sale, actor)
    finish_idempotency(db, actor, "venta", key, digest, sale.id)
    return response(sale)


def sale_for_order(db, actor, order):
    sale = db.scalar(select(Sale).where(Sale.pedido_id == order.id).with_for_update())
    if sale is not None:
        return sale
    if order.estado in {"CANCELADO", "ENTREGADO"}:
        raise HTTPException(
            409, "Pedido histórico finalizado; requiere conciliación administrativa"
        )
    sale = Sale(
        numero_venta="VEN-" + uuid4().hex,
        cliente_id=order.cliente_id,
        sucursal_id=order.sucursal_id,
        pedido_id=order.id,
        tipo="EN_LINEA",
        subtotal=order.subtotal,
        descuento=order.descuento,
        total=order.total,
        vence_at=utcnow() + timedelta(hours=24),
    )
    db.add(sale)
    db.flush()
    for d in order.detalles:
        product = db.get(Product, d.producto_id)
        db.add(
            SaleDetail(
                venta_id=sale.id,
                producto_id=d.producto_id,
                cantidad=d.cantidad,
                precio_unitario=d.precio_unitario,
                descuento=d.descuento,
                subtotal=d.subtotal,
                producto_nombre=product.nombre if product else None,
                producto_sku=product.sku if product else None,
            )
        )
    db.flush()
    db.refresh(sale, attribute_names=["detalles"])
    record(
        db,
        "VENTA",
        sale,
        actor,
        reason="Vinculada al pedido; reserva existente, sin doble descuento",
    )
    return sale


def cancel_locked(db, actor, sale, data):
    if sale.vence_at is None:
        raise HTTPException(
            409, "Venta histórica sin reserva verificable; requiere conciliación"
        )
    if sale.estado == "CANCELADA":
        raise HTTPException(409, "La venta ya está cancelada")
    order = db.get(Order, sale.pedido_id) if sale.pedido_id else None
    if order and order.estado == "ENTREGADO":
        raise HTTPException(409, "Pedido entregado; devolución fuera de este flujo")
    if actor.rol_id == RoleID.CLIENTE and (
        sale.estado != "PENDIENTE" or (order and order.estado != "PENDIENTE")
    ):
        raise HTTPException(
            403, "El cliente sólo puede cancelar pedidos pendientes sin pago confirmado"
        )
    invoice = db.scalar(select(Invoice).where(Invoice.venta_id == sale.id))
    if invoice and invoice.estado == "EMITIDA":
        raise HTTPException(409, "Registra primero la cancelación fiscal externa")
    payments = list(
        db.scalars(
            select(Payment)
            .where(Payment.venta_id == sale.id)
            .order_by(Payment.id)
            .with_for_update()
        )
    )
    for p in payments:
        if p.estado == "APROBADO":
            if actor.rol_id != RoleID.ADMINISTRADOR:
                raise HTTPException(
                    403, "Sólo administrador puede registrar devolución"
                )
            if not data.reembolso_referencia:
                raise HTTPException(
                    409, "Se requiere referencia de devolución manual completa"
                )
            p.estado = "REEMBOLSADO"
            record(db, "PAGO", p, actor, "APROBADO", data.reembolso_referencia)
        elif p.estado in {"PENDIENTE", "EN_PROCESO"}:
            old = p.estado
            p.estado = "CANCELADO"
            record(db, "PAGO", p, actor, old, data.motivo)
    move_stock(
        db,
        sale.sucursal_id,
        sale.detalles,
        restore=True,
        resource="PEDIDO" if order else "VENTA",
        resource_id=order.id if order else sale.id,
        actor_id=actor.id,
    )
    if order:
        old = order.estado
        order.estado = "CANCELADO"
        record(db, "PEDIDO", order, actor, old, data.motivo)
    if invoice and invoice.estado == "PENDIENTE":
        invoice.estado = "CANCELADA"
        record(db, "FACTURA", invoice, actor, "PENDIENTE", data.motivo)
    old = sale.estado
    sale.estado = "CANCELADA"
    record(db, "VENTA", sale, actor, old, data.motivo)
    return response(sale)


@atomic
def cancel_sale(db, actor, sale_id, data):
    return cancel_locked(db, actor, get_sale(db, actor, sale_id, lock=True), data)


@atomic
def expire_sales(db, actor, limit=100):
    from app.shared.commerce import CancelRequest

    ids = list(
        db.scalars(
            select(Sale.id)
            .where(Sale.estado == "PENDIENTE", Sale.vence_at <= utcnow())
            .order_by(Sale.id)
            .limit(limit)
        )
    )
    cancelled = []
    for sid in ids:
        sale = get_sale(db, actor, sid, lock=True)
        if sale.estado == "PENDIENTE" and expired(sale.vence_at):
            cancel_locked(
                db, actor, sale, CancelRequest(motivo="Vencimiento de reserva sin pago")
            )
            cancelled.append(sid)
    return {"ventas_canceladas": cancelled}
