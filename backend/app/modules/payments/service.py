from fastapi import HTTPException
from sqlalchemy import select
from app.core.permissions import RoleID
from app.modules.orders.model import Order
from app.modules.sales.repository import get_sale
from app.modules.sales.service import sale_for_order
from app.modules.payments.model import Payment, PaymentMethod
from app.modules.payments.repository import get_payment
from app.modules.payments.schemas import PaymentResponse
from app.shared.commerce import (
    atomic,
    authorize,
    begin_idempotency,
    finish_idempotency,
    expired,
    record,
    utcnow,
)


@atomic
def create_payment(db, actor, data, key):
    prior, digest = begin_idempotency(
        db, actor, "pago", key, data.model_dump(mode="json")
    )
    if prior:
        return PaymentResponse.model_validate(get_payment(db, actor, prior)[0])
    if data.pedido_id is not None:
        order = db.scalar(
            select(Order)
            .where(Order.id == data.pedido_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if order is None:
            raise HTTPException(404, "Pedido no encontrado")
        authorize(db, actor, order)
        sale = sale_for_order(db, actor, order)
    else:
        sale = get_sale(db, actor, data.venta_id, lock=True)
    if sale.vence_at is None:
        raise HTTPException(
            409, "Venta histórica sin reserva verificable; requiere conciliación"
        )
    if sale.estado != "PENDIENTE" or expired(sale.vence_at):
        raise HTTPException(
            409, "La operación no admite pagos; comprueba su estado o vencimiento"
        )
    if data.monto != sale.total:
        raise HTTPException(409, "El pago debe cubrir exactamente el total")
    if actor.rol_id == RoleID.CLIENTE and data.metodo not in {"SPEI", "DEPOSITO"}:
        raise HTTPException(403, "El personal registra efectivo y terminal física")
    method = db.scalar(
        select(PaymentMethod)
        .where(PaymentMethod.codigo == data.metodo, PaymentMethod.activo.is_(True))
        .with_for_update(read=True)
    )
    if method is None:
        raise HTTPException(409, "Método de pago no disponible")
    if db.scalar(
        select(Payment.id).where(
            Payment.venta_id == sale.id,
            Payment.estado.in_(["PENDIENTE", "EN_PROCESO", "APROBADO"]),
        )
    ):
        raise HTTPException(409, "La operación ya tiene un pago activo")
    payment = Payment(
        venta_id=sale.id,
        metodo_pago_id=method.id,
        monto=data.monto,
        referencia=data.referencia,
    )
    db.add(payment)
    db.flush()
    record(db, "PAGO", payment, actor)
    finish_idempotency(db, actor, "pago", key, digest, payment.id)
    return PaymentResponse.model_validate(payment)


@atomic
def transition_payment(db, actor, payment_id, data):
    if actor.rol_id not in {RoleID.ADMINISTRADOR, RoleID.EMPLEADO}:
        raise HTTPException(403, "Sólo personal puede verificar pagos")
    payment, sale = get_payment(db, actor, payment_id, lock=True)
    if payment.estado != "PENDIENTE":
        raise HTTPException(409, "El pago ya fue procesado")
    if payment.proveedor != "INTERNO":
        raise HTTPException(
            409, "Pago histórico de proveedor externo; conciliar por separado"
        )
    if sale.estado != "PENDIENTE":
        raise HTTPException(409, "Venta no pendiente")
    if data.estado == "APROBADO":
        if sale.vence_at is None:
            raise HTTPException(
                409, "Venta histórica sin reserva verificable; requiere conciliación"
            )
        if expired(sale.vence_at):
            raise HTTPException(
                409, "Reserva vencida; cancelar antes de crear otra operación"
            )
        if payment.monto != sale.total:
            raise HTTPException(409, "Importe inconsistente")
        payment.paid_at = utcnow()
        payment.confirmado_por = actor.id
        old = sale.estado
        sale.estado = "CONFIRMADA"
        record(db, "VENTA", sale, actor, old, "Pago verificado manualmente")
        if sale.pedido_id:
            order = db.get(Order, sale.pedido_id)
            if order.estado == "CANCELADO":
                raise HTTPException(409, "Pedido cancelado")
            if order.estado == "PENDIENTE":
                order.estado = "CONFIRMADO"
                record(
                    db,
                    "PEDIDO",
                    order,
                    actor,
                    "PENDIENTE",
                    "Pago verificado manualmente",
                )
    payment.estado = data.estado
    record(db, "PAGO", payment, actor, "PENDIENTE", data.motivo)
    return PaymentResponse.model_validate(payment)
