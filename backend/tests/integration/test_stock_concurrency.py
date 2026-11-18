"""Real PostgreSQL lock and identity-map regression tests."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func
from app.modules.inventory.model import Inventory, InventoryMovement
from app.modules.inventory.repository import inventory_repository
from app.modules.inventory.service import inventory_service
from app.modules.inventory.schemas import InventoryMovementCreate
from app.modules.orders.model import Order
from app.modules.orders.service import order_service
from app.modules.orders.schemas import OrderCreate, OrderStatusUpdate


def payload(ids, quantity=7):
    return OrderCreate(
        cliente_id=ids["customer"],
        sucursal_id=ids["branch"],
        productos=[{"producto_id": ids["product"], "cantidad": quantity}],
    )


def test_lock_refreshes_preloaded_stock(pg_case):
    factory, ids = pg_case
    with factory() as first, factory() as second:
        stale = first.get(Inventory, ids["inventory"])
        assert stale.cantidad == 10
        inventory_service.register_exit(
            second, ids["inventory"], InventoryMovementCreate(cantidad=7)
        )
        result = inventory_service.register_entry(
            first, ids["inventory"], InventoryMovementCreate(cantidad=1)
        )
        assert result.cantidad == 4


def test_two_orders_cannot_oversell(pg_case):
    factory, ids = pg_case
    barrier = Barrier(2)
    original = inventory_repository.get_by_id

    def synchronized(db, inventory_id, *, for_update=False):
        if for_update:
            barrier.wait(timeout=10)
        return original(db, inventory_id, for_update=for_update)

    def create(_):
        with factory() as db:
            try:
                order_service.create(db, payload(ids))
                return 201
            except HTTPException as exc:
                return exc.status_code

    with patch.object(inventory_repository, "get_by_id", side_effect=synchronized):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(create, range(2)))
    assert sorted(results) == [201, 409]
    with factory() as db:
        assert db.get(Inventory, ids["inventory"]).cantidad == 3
        assert db.scalar(select(func.count()).select_from(Order)) == 1
        assert db.scalar(select(func.count()).select_from(InventoryMovement)) == 1


def test_stale_order_cannot_restore_stock_twice(pg_case):
    factory, ids = pg_case
    with factory() as db:
        created = order_service.create(db, payload(ids, 3))
    with factory() as first, factory() as second:
        stale = first.get(Order, created.id)
        assert stale.estado == "PENDIENTE"
        order_service.update_status(
            second, created.id, OrderStatusUpdate(estado="CANCELADO")
        )
        with pytest.raises(HTTPException) as exc:
            order_service.update_status(
                first, created.id, OrderStatusUpdate(estado="CANCELADO")
            )
        assert exc.value.status_code == 409
    with factory() as db:
        assert db.get(Inventory, ids["inventory"]).cantidad == 10
