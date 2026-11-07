
"""Pruebas unitarias del servicio de pedidos, sin base de datos real."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, call, patch

import pytest
from fastapi import HTTPException

# Registrar los modelos relacionados.
from app.modules.categories.model import Category
from app.modules.branches.model import Branch
from app.modules.customers.model import Customer
from app.modules.products.model import Product
from app.modules.inventory.model import Inventory, InventoryMovement
from app.modules.orders.model import Order, OrderDetail

from app.modules.orders.schemas import (
    OrderCreate,
    OrderItemCreate,
    OrderStatus,
    OrderStatusUpdate,
)
from app.modules.orders.service import OrderService


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def service():
    return OrderService()


@pytest.fixture
def db():
    return MagicMock()


@pytest.fixture
def repositories():
    with (
        patch(
            "app.modules.orders.service.order_repository"
        ) as orders,
        patch(
            "app.modules.orders.service.inventory_repository"
        ) as inventory,
    ):
        yield orders, inventory


@pytest.fixture
def order():
    now = datetime.now(timezone.utc)

    result = Order(
        id=50,
        numero_pedido="PED-TEST-0001",
        cliente_id=1,
        sucursal_id=2,
        estado="PENDIENTE",
        subtotal=Decimal("60.00"),
        descuento=Decimal("0.00"),
        total=Decimal("60.00"),
        fecha_pedido=now,
        created_at=now,
        updated_at=now,
    )

    result.detalles = [
        OrderDetail(
            id=100,
            pedido_id=50,
            producto_id=10,
            cantidad=2,
            precio_unitario=Decimal("30.00"),
            descuento=Decimal("0.00"),
            subtotal=Decimal("60.00"),
        )
    ]

    return result


@pytest.fixture
def stock():
    return Inventory(
        id=5,
        producto_id=10,
        sucursal_id=2,
        cantidad=10,
        stock_minimo=2,
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def payload():
    return OrderCreate(
        cliente_id=1,
        sucursal_id=2,
        productos=[
            OrderItemCreate(
                producto_id=10,
                cantidad=2,
            )
        ],
    )


def configure_create(repositories, order, stock):
    orders, inventory = repositories

    orders.get_customer.return_value = MagicMock(
        activo=True
    )
    orders.get_branch.return_value = MagicMock(
        activo=True
    )
    orders.get_product.return_value = MagicMock(
        activo=True,
        precio=Decimal("30.00"),
    )
    orders.get_inventory.return_value = stock
    orders.create.return_value = order
    orders.get_by_id.return_value = order

    inventory.get_by_id.return_value = stock

    return orders, inventory


# ============================================================
# CONSULTAS
# ============================================================


def test_get_by_id(service, db, repositories, order):
    orders, _ = repositories
    orders.get_by_id.return_value = order

    result = service.get_by_id(db, 50)

    assert result.id == 50
    assert result.numero_pedido == "PED-TEST-0001"
    assert len(result.detalles) == 1


def test_get_by_id_missing(service, db, repositories):
    orders, _ = repositories
    orders.get_by_id.return_value = None

    with pytest.raises(HTTPException) as error:
        service.get_by_id(db, 999)

    assert error.value.status_code == 404


def test_get_by_number(service, db, repositories, order):
    orders, _ = repositories
    orders.get_by_number.return_value = order

    result = service.get_by_number(
        db,
        "PED-TEST-0001",
    )

    assert result.id == 50


def test_get_by_number_missing(service, db, repositories):
    orders, _ = repositories
    orders.get_by_number.return_value = None

    with pytest.raises(HTTPException) as error:
        service.get_by_number(db, "NO-EXISTE")

    assert error.value.status_code == 404


def test_get_all(service, db, repositories, order):
    orders, _ = repositories

    orders.get_all.return_value = [order]
    orders.count.return_value = 1

    result = service.get_all(
        db,
        cliente_id=1,
        estado=OrderStatus.PENDIENTE,
        limit=10,
        offset=0,
    )

    assert result.total == 1
    assert len(result.pedidos) == 1

    orders.get_all.assert_called_once_with(
        db,
        cliente_id=1,
        sucursal_id=None,
        estado="PENDIENTE",
        limit=10,
        offset=0,
    )


@pytest.mark.parametrize(
    ("limit", "offset"),
    [(0, 0), (101, 0), (20, -1)],
)
def test_get_all_invalid_pagination(
    service, db, limit, offset
):
    with pytest.raises(HTTPException) as error:
        service.get_all(
            db,
            limit=limit,
            offset=offset,
        )

    assert error.value.status_code == 422


# ============================================================
# CREACION DE PEDIDOS
# ============================================================


def test_create_order(
    service, db, repositories, order, stock, payload
):
    orders, inventory = configure_create(
        repositories, order, stock
    )

    result = service.create(
        db,
        payload,
        usuario_id=7,
    )

    assert result.id == 50

    orders.create.assert_called_once()
    arguments = orders.create.call_args.kwargs

    assert arguments["subtotal"] == Decimal("60.00")
    assert arguments["total"] == Decimal("60.00")
    assert arguments["descuento"] == Decimal("0.00")

    orders.create_details.assert_called_once()
    details = orders.create_details.call_args.kwargs["items"]

    assert len(details) == 1
    assert details[0]["cantidad"] == 2
    assert details[0]["subtotal"] == Decimal("60.00")

    inventory.update_quantity.assert_called_once_with(
        db, stock, 8
    )

    inventory.create_movement.assert_called_once_with(
        db,
        inventario_id=5,
        tipo="SALIDA",
        cantidad=2,
        motivo="Reserva de existencias por pedido",
        referencia_tipo="PEDIDO",
        referencia_id=50,
        usuario_id=7,
    )

    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_create_missing_customer(
    service, db, repositories, payload
):
    orders, _ = repositories
    orders.get_customer.return_value = None

    with pytest.raises(HTTPException) as error:
        service.create(db, payload)

    assert error.value.status_code == 404
    orders.create.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_create_inactive_customer(
    service, db, repositories, payload
):
    orders, _ = repositories
    orders.get_customer.return_value = MagicMock(
        activo=False
    )

    with pytest.raises(HTTPException) as error:
        service.create(db, payload)

    assert error.value.status_code == 409
    db.commit.assert_not_called()


def test_create_missing_branch(
    service, db, repositories, payload
):
    orders, _ = repositories
    orders.get_customer.return_value = MagicMock(
        activo=True
    )
    orders.get_branch.return_value = None

    with pytest.raises(HTTPException) as error:
        service.create(db, payload)

    assert error.value.status_code == 404
    db.commit.assert_not_called()


def test_create_inactive_branch(
    service, db, repositories, payload
):
    orders, _ = repositories
    orders.get_customer.return_value = MagicMock(
        activo=True
    )
    orders.get_branch.return_value = MagicMock(
        activo=False
    )

    with pytest.raises(HTTPException) as error:
        service.create(db, payload)

    assert error.value.status_code == 409
    db.commit.assert_not_called()


def test_create_missing_product(
    service, db, repositories, order, stock, payload
):
    orders, _ = configure_create(
        repositories, order, stock
    )
    orders.get_product.return_value = None

    with pytest.raises(HTTPException) as error:
        service.create(db, payload)

    assert error.value.status_code == 404
    orders.create.assert_not_called()


def test_create_inactive_product(
    service, db, repositories, order, stock, payload
):
    orders, _ = configure_create(
        repositories, order, stock
    )
    orders.get_product.return_value = MagicMock(
        activo=False
    )

    with pytest.raises(HTTPException) as error:
        service.create(db, payload)

    assert error.value.status_code == 409
    orders.create.assert_not_called()


def test_create_missing_inventory(
    service, db, repositories, order, stock, payload
):
    orders, _ = configure_create(
        repositories, order, stock
    )
    orders.get_inventory.return_value = None

    with pytest.raises(HTTPException) as error:
        service.create(db, payload)

    assert error.value.status_code == 409
    orders.create.assert_not_called()


def test_create_insufficient_stock(
    service, db, repositories, order, stock, payload
):
    orders, inventory = configure_create(
        repositories, order, stock
    )
    stock.cantidad = 1

    with pytest.raises(HTTPException) as error:
        service.create(db, payload)

    assert error.value.status_code == 409

    orders.create.assert_not_called()
    inventory.update_quantity.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_create_invalid_price(
    service, db, repositories, order, stock, payload
):
    orders, _ = configure_create(
        repositories, order, stock
    )
    orders.get_product.return_value = MagicMock(
        activo=True,
        precio=Decimal("-1.00"),
    )

    with pytest.raises(HTTPException) as error:
        service.create(db, payload)

    assert error.value.status_code == 409
    orders.create.assert_not_called()


def test_create_rolls_back_on_movement_failure(
    service, db, repositories, order, stock, payload
):
    _, inventory = configure_create(
        repositories, order, stock
    )

    inventory.create_movement.side_effect = RuntimeError(
        "movement failure"
    )

    with pytest.raises(RuntimeError):
        service.create(db, payload)

    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_create_locks_inventory(
    service, db, repositories, order, stock, payload
):
    configure_create(repositories, order, stock)
    _, inventory = repositories

    service.create(db, payload)

    inventory.get_by_id.assert_called_once_with(
        db, 5, for_update=True
    )


# ============================================================
# CAMBIOS DE ESTADO Y CANCELACION
# ============================================================


def test_confirm_order(
    service, db, repositories, order
):
    orders, _ = repositories
    orders.get_by_id.return_value = order

    result = service.update_status(
        db,
        50,
        OrderStatusUpdate(
            estado=OrderStatus.CONFIRMADO
        ),
    )

    assert result.id == 50

    orders.update_status.assert_called_once_with(
        db, order, "CONFIRMADO"
    )
    db.commit.assert_called_once()


def test_cancel_order_restores_inventory(
    service, db, repositories, order, stock
):
    orders, inventory = repositories

    orders.get_by_id.return_value = order
    orders.get_inventory.return_value = stock
    inventory.get_by_id.return_value = stock

    service.update_status(
        db,
        50,
        OrderStatusUpdate(
            estado=OrderStatus.CANCELADO
        ),
        usuario_id=7,
    )

    inventory.update_quantity.assert_called_once_with(
        db, stock, 12
    )

    inventory.create_movement.assert_called_once_with(
        db,
        inventario_id=5,
        tipo="ENTRADA",
        cantidad=2,
        motivo="Reposición por cancelación de pedido",
        referencia_tipo="PEDIDO",
        referencia_id=50,
        usuario_id=7,
    )

    db.commit.assert_called_once()


def test_cancel_order_twice_rejected(
    service, db, repositories, order
):
    orders, inventory = repositories
    order.estado = "CANCELADO"
    orders.get_by_id.return_value = order

    with pytest.raises(HTTPException) as error:
        service.update_status(
            db,
            50,
            OrderStatusUpdate(
                estado=OrderStatus.CANCELADO
            ),
        )

    assert error.value.status_code == 409
    inventory.update_quantity.assert_not_called()
    db.commit.assert_not_called()


def test_delivered_order_cannot_be_cancelled(
    service, db, repositories, order
):
    orders, inventory = repositories
    order.estado = "ENTREGADO"
    orders.get_by_id.return_value = order

    with pytest.raises(HTTPException) as error:
        service.update_status(
            db,
            50,
            OrderStatusUpdate(
                estado=OrderStatus.CANCELADO
            ),
        )

    assert error.value.status_code == 409
    inventory.update_quantity.assert_not_called()
    db.commit.assert_not_called()


def test_invalid_status_transition(
    service, db, repositories, order
):
    orders, _ = repositories
    orders.get_by_id.return_value = order

    with pytest.raises(HTTPException) as error:
        service.update_status(
            db,
            50,
            OrderStatusUpdate(
                estado=OrderStatus.ENTREGADO
            ),
        )

    assert error.value.status_code == 409
    orders.update_status.assert_not_called()
    db.rollback.assert_called_once()


def test_cancel_rolls_back_on_movement_failure(
    service, db, repositories, order, stock
):
    orders, inventory = repositories

    orders.get_by_id.return_value = order
    orders.get_inventory.return_value = stock
    inventory.get_by_id.return_value = stock

    inventory.create_movement.side_effect = RuntimeError(
        "movement failure"
    )

    with pytest.raises(RuntimeError):
        service.update_status(
            db,
            50,
            OrderStatusUpdate(
                estado=OrderStatus.CANCELADO
            ),
        )

    db.rollback.assert_called_once()
    db.commit.assert_not_called()
    orders.update_status.assert_not_called()


def test_cancel_missing_inventory(
    service, db, repositories, order
):
    orders, inventory = repositories

    orders.get_by_id.return_value = order
    orders.get_inventory.return_value = None

    with pytest.raises(HTTPException) as error:
        service.update_status(
            db,
            50,
            OrderStatusUpdate(
                estado=OrderStatus.CANCELADO
            ),
        )

    assert error.value.status_code == 409
    inventory.update_quantity.assert_not_called()
    db.rollback.assert_called_once()


# ============================================================
# VALIDACIONES DE ESQUEMAS
# ============================================================


def test_create_requires_products():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        OrderCreate(
            cliente_id=1,
            sucursal_id=2,
            productos=[],
        )


def test_create_rejects_duplicate_products():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        OrderCreate(
            cliente_id=1,
            sucursal_id=2,
            productos=[
                OrderItemCreate(
                    producto_id=10,
                    cantidad=1,
                ),
                OrderItemCreate(
                    producto_id=10,
                    cantidad=2,
                ),
            ],
        )


def test_create_rejects_zero_quantity():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        OrderItemCreate(
            producto_id=10,
            cantidad=0,
        )
