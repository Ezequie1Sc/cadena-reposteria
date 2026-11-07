
"""Pruebas unitarias del servicio de inventarios, sin base de datos real."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, call, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

# Registrar modelos relacionados antes de crear instancias ORM.
from app.modules.categories.model import Category
from app.modules.branches.model import Branch
from app.modules.products.model import Product
from app.modules.inventory.model import Inventory, InventoryMovement

from app.modules.inventory.schemas import (
    InventoryAdjustmentCreate,
    InventoryCreate,
    InventoryMovementCreate,
    InventoryTransferCreate,
    InventoryUpdate,
    MovementType,
)
from app.modules.inventory.service import InventoryService


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def service():
    return InventoryService()


@pytest.fixture
def db():
    return MagicMock()


@pytest.fixture
def repository():
    with patch(
        "app.modules.inventory.service.inventory_repository"
    ) as mock:
        yield mock


@pytest.fixture
def inventory():
    return Inventory(
        id=1,
        producto_id=10,
        sucursal_id=20,
        cantidad=15,
        stock_minimo=5,
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def destination():
    return Inventory(
        id=2,
        producto_id=10,
        sucursal_id=21,
        cantidad=4,
        stock_minimo=2,
        updated_at=datetime.now(timezone.utc),
    )


def configure_active_entities(db):
    """Simula productos y sucursales activos."""

    def get_entity(model, entity_id):
        if model is Product:
            return MagicMock(activo=True)

        if model is Branch:
            return MagicMock(activo=True)

        raise AssertionError(
            f"Modelo inesperado: {model}"
        )

    db.get.side_effect = get_entity


def configure_transfer(
    repository,
    inventory,
    destination,
):
    """Configura las consultas simuladas de un traspaso."""

    repository.get_by_product_and_branch.return_value = (
        destination
    )

    def get_inventory(
        db_session,
        inventory_id,
        for_update=False,
    ):
        if inventory_id == inventory.id:
            return inventory

        if inventory_id == destination.id:
            return destination

        return None

    repository.get_by_id.side_effect = get_inventory


# ============================================================
# CONSULTAS
# ============================================================


def test_get_all_with_filters(
    service,
    db,
    repository,
    inventory,
):
    repository.get_all.return_value = [inventory]

    result = service.get_all(
        db,
        sucursal_id=20,
        producto_id=10,
        solo_bajo_stock=True,
    )

    assert result.total == 1
    assert result.inventarios[0].cantidad == 15

    repository.get_all.assert_called_once_with(
        db,
        sucursal_id=20,
        producto_id=10,
        solo_bajo_stock=True,
    )


def test_get_by_id(
    service,
    db,
    repository,
    inventory,
):
    repository.get_by_id.return_value = inventory

    result = service.get_by_id(db, 1)

    assert result.id == 1
    assert result.cantidad == 15

    repository.get_by_id.assert_called_once_with(
        db,
        1,
        for_update=False,
    )


def test_missing_inventory_returns_404(
    service,
    db,
    repository,
):
    repository.get_by_id.return_value = None

    with pytest.raises(HTTPException) as error:
        service.get_by_id(db, 999)

    assert error.value.status_code == 404


# ============================================================
# VALIDACIONES DE PRODUCTOS Y SUCURSALES
# ============================================================


@pytest.mark.parametrize(
    ("missing_model", "status_code"),
    [
        (Product, 404),
        (Branch, 404),
    ],
)
def test_create_rejects_missing_entity(
    service,
    db,
    repository,
    missing_model,
    status_code,
):
    configure_active_entities(db)

    original = db.get.side_effect

    def get_entity(model, entity_id):
        if model is missing_model:
            return None

        return original(model, entity_id)

    db.get.side_effect = get_entity

    with pytest.raises(HTTPException) as error:
        service.create(
            db,
            InventoryCreate(
                producto_id=10,
                sucursal_id=20,
            ),
        )

    assert error.value.status_code == status_code

    repository.create.assert_not_called()


@pytest.mark.parametrize(
    "inactive_model",
    [
        Product,
        Branch,
    ],
)
def test_create_rejects_inactive_entity(
    service,
    db,
    repository,
    inactive_model,
):
    configure_active_entities(db)

    original = db.get.side_effect

    def get_entity(model, entity_id):
        if model is inactive_model:
            return MagicMock(activo=False)

        return original(model, entity_id)

    db.get.side_effect = get_entity

    with pytest.raises(HTTPException) as error:
        service.create(
            db,
            InventoryCreate(
                producto_id=10,
                sucursal_id=20,
            ),
        )

    assert error.value.status_code == 409

    repository.create.assert_not_called()


# ============================================================
# CREACION DE INVENTARIOS
# ============================================================


def test_create_inventory(
    service,
    db,
    repository,
    inventory,
):
    configure_active_entities(db)

    repository.get_by_product_and_branch.return_value = None
    repository.create.return_value = inventory

    result = service.create(
        db,
        InventoryCreate(
            producto_id=10,
            sucursal_id=20,
            stock_minimo=5,
        ),
    )

    assert result.id == 1
    assert result.producto_id == 10
    assert result.sucursal_id == 20

    repository.create.assert_called_once_with(
        db,
        producto_id=10,
        sucursal_id=20,
        stock_minimo=5,
    )

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(inventory)


def test_create_rejects_duplicate(
    service,
    db,
    repository,
    inventory,
):
    configure_active_entities(db)

    repository.get_by_product_and_branch.return_value = (
        inventory
    )

    with pytest.raises(HTTPException) as error:
        service.create(
            db,
            InventoryCreate(
                producto_id=10,
                sucursal_id=20,
            ),
        )

    assert error.value.status_code == 409

    repository.create.assert_not_called()
    db.commit.assert_not_called()


def test_create_rolls_back_integrity_error(
    service,
    db,
    repository,
):
    configure_active_entities(db)

    repository.get_by_product_and_branch.return_value = None

    repository.create.side_effect = IntegrityError(
        "INSERT",
        {},
        Exception("duplicate"),
    )

    with pytest.raises(HTTPException) as error:
        service.create(
            db,
            InventoryCreate(
                producto_id=10,
                sucursal_id=20,
            ),
        )

    assert error.value.status_code == 409

    db.rollback.assert_called_once()
    db.commit.assert_not_called()


# ============================================================
# STOCK MINIMO
# ============================================================


def test_update_minimum_stock(
    service,
    db,
    repository,
    inventory,
):
    repository.get_by_id.return_value = inventory

    result = service.update_minimum_stock(
        db,
        1,
        InventoryUpdate(stock_minimo=8),
    )

    assert result.id == 1

    repository.get_by_id.assert_called_once_with(
        db,
        1,
        for_update=True,
    )

    repository.update_minimum_stock.assert_called_once_with(
        db,
        inventory,
        8,
    )

    db.commit.assert_called_once()


def test_update_minimum_stock_rolls_back_on_failure(
    service,
    db,
    repository,
    inventory,
):
    repository.get_by_id.return_value = inventory

    repository.update_minimum_stock.side_effect = (
        RuntimeError("database failure")
    )

    with pytest.raises(RuntimeError):
        service.update_minimum_stock(
            db,
            1,
            InventoryUpdate(stock_minimo=8),
        )

    db.rollback.assert_called_once()
    db.commit.assert_not_called()


# ============================================================
# ENTRADAS Y SALIDAS
# ============================================================


@pytest.mark.parametrize(
    (
        "method",
        "quantity",
        "expected",
        "movement_type",
    ),
    [
        (
            "register_entry",
            6,
            21,
            MovementType.ENTRADA,
        ),
        (
            "register_exit",
            4,
            11,
            MovementType.SALIDA,
        ),
    ],
)
def test_entry_and_exit(
    service,
    db,
    repository,
    inventory,
    method,
    quantity,
    expected,
    movement_type,
):
    configure_active_entities(db)

    repository.get_by_id.return_value = inventory

    result = getattr(service, method)(
        db,
        1,
        InventoryMovementCreate(
            cantidad=quantity,
            motivo="Control",
        ),
        usuario_id=7,
    )

    assert result.id == 1

    repository.update_quantity.assert_called_once_with(
        db,
        inventory,
        expected,
    )

    repository.create_movement.assert_called_once_with(
        db,
        inventario_id=1,
        tipo=movement_type.value,
        cantidad=quantity,
        motivo="Control",
        referencia_tipo=None,
        referencia_id=None,
        usuario_id=7,
    )

    db.commit.assert_called_once()


def test_exit_rejects_insufficient_stock(
    service,
    db,
    repository,
    inventory,
):
    configure_active_entities(db)

    repository.get_by_id.return_value = inventory

    with pytest.raises(HTTPException) as error:
        service.register_exit(
            db,
            1,
            InventoryMovementCreate(
                cantidad=16,
            ),
        )

    assert error.value.status_code == 409

    repository.update_quantity.assert_not_called()
    repository.create_movement.assert_not_called()

    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_entry_rolls_back_if_movement_fails(
    service,
    db,
    repository,
    inventory,
):
    configure_active_entities(db)

    repository.get_by_id.return_value = inventory

    repository.create_movement.side_effect = (
        RuntimeError("movement failure")
    )

    with pytest.raises(RuntimeError):
        service.register_entry(
            db,
            1,
            InventoryMovementCreate(
                cantidad=2,
            ),
        )

    db.rollback.assert_called_once()
    db.commit.assert_not_called()


# ============================================================
# VENTAS
# ============================================================


def test_register_sale_records_reference(
    service,
    db,
    repository,
    inventory,
):
    configure_active_entities(db)

    repository.get_by_id.return_value = inventory

    service.register_sale(
        db,
        1,
        3,
        usuario_id=7,
        referencia_id=50,
    )

    repository.update_quantity.assert_called_once_with(
        db,
        inventory,
        12,
    )

    repository.create_movement.assert_called_once_with(
        db,
        inventario_id=1,
        tipo="VENTA",
        cantidad=3,
        motivo="Venta de producto",
        referencia_tipo="VENTA",
        referencia_id=50,
        usuario_id=7,
    )

    db.commit.assert_called_once()


def test_register_sale_rejects_nonpositive_quantity(
    service,
    db,
    repository,
):
    with pytest.raises(HTTPException) as error:
        service.register_sale(
            db,
            1,
            0,
        )

    assert error.value.status_code == 422

    repository.update_quantity.assert_not_called()
    db.commit.assert_not_called()


# ============================================================
# AJUSTES DE INVENTARIO
# ============================================================


@pytest.mark.parametrize(
    (
        "final_quantity",
        "movement_quantity",
        "direction",
    ),
    [
        (20, 5, "INCREMENTO"),
        (9, 6, "DISMINUCION"),
    ],
)
def test_adjust_stock(
    service,
    db,
    repository,
    inventory,
    final_quantity,
    movement_quantity,
    direction,
):
    configure_active_entities(db)

    repository.get_by_id.return_value = inventory

    result = service.adjust_stock(
        db,
        1,
        InventoryAdjustmentCreate(
            cantidad_final=final_quantity,
            motivo="Conteo",
        ),
        usuario_id=7,
    )

    assert result.id == 1

    repository.update_quantity.assert_called_once_with(
        db,
        inventory,
        final_quantity,
    )

    repository.create_movement.assert_called_once_with(
        db,
        inventario_id=1,
        tipo="AJUSTE",
        cantidad=movement_quantity,
        motivo=f"{direction}: Conteo",
        usuario_id=7,
    )

    db.commit.assert_called_once()


def test_adjust_unchanged_stock_creates_no_movement(
    service,
    db,
    repository,
    inventory,
):
    configure_active_entities(db)

    repository.get_by_id.return_value = inventory

    result = service.adjust_stock(
        db,
        1,
        InventoryAdjustmentCreate(
            cantidad_final=15,
            motivo="Conteo",
        ),
    )

    assert result.cantidad == 15

    repository.update_quantity.assert_not_called()
    repository.create_movement.assert_not_called()
    db.commit.assert_not_called()


# ============================================================
# TRASPASOS ENTRE SUCURSALES
# ============================================================


def test_transfer_updates_both_inventories(
    service,
    db,
    repository,
    inventory,
    destination,
):
    configure_active_entities(db)

    configure_transfer(
        repository,
        inventory,
        destination,
    )

    result = service.transfer(
        db,
        1,
        InventoryTransferCreate(
            sucursal_destino_id=21,
            cantidad=6,
            motivo="Reposicion",
        ),
        usuario_id=7,
    )

    assert result.origen.id == 1
    assert result.destino.id == 2

    assert repository.update_quantity.call_args_list == [
        call(db, inventory, 9),
        call(db, destination, 10),
    ]

    assert repository.create_movement.call_count == 2

    first, second = (
        repository.create_movement.call_args_list
    )

    assert (
        first.kwargs["referencia_tipo"]
        == "INVENTARIO_DESTINO"
    )
    assert first.kwargs["referencia_id"] == 2

    assert (
        second.kwargs["referencia_tipo"]
        == "INVENTARIO_ORIGEN"
    )
    assert second.kwargs["referencia_id"] == 1

    db.commit.assert_called_once()

    db.refresh.assert_has_calls(
        [
            call(inventory),
            call(destination),
        ]
    )


def test_transfer_locks_in_id_order(
    service,
    db,
    repository,
    inventory,
    destination,
):
    configure_active_entities(db)

    configure_transfer(
        repository,
        inventory,
        destination,
    )

    repository.get_by_product_and_branch.return_value = (
        inventory
    )

    service.transfer(
        db,
        2,
        InventoryTransferCreate(
            sucursal_destino_id=20,
            cantidad=2,
        ),
    )

    locked_ids = [
        item.args[1]
        for item in repository.get_by_id.call_args_list
        if item.kwargs.get("for_update") is True
    ]

    assert locked_ids == [1, 2]


def test_transfer_rejects_same_branch(
    service,
    db,
    repository,
    inventory,
):
    repository.get_by_id.return_value = inventory

    with pytest.raises(HTTPException) as error:
        service.transfer(
            db,
            1,
            InventoryTransferCreate(
                sucursal_destino_id=20,
                cantidad=1,
            ),
        )

    assert error.value.status_code == 422

    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_transfer_requires_destination_inventory(
    service,
    db,
    repository,
    inventory,
):
    configure_active_entities(db)

    repository.get_by_id.return_value = inventory
    repository.get_by_product_and_branch.return_value = None

    with pytest.raises(HTTPException) as error:
        service.transfer(
            db,
            1,
            InventoryTransferCreate(
                sucursal_destino_id=21,
                cantidad=1,
            ),
        )

    assert error.value.status_code == 404

    db.rollback.assert_called_once()


def test_transfer_rejects_insufficient_stock(
    service,
    db,
    repository,
    inventory,
    destination,
):
    configure_active_entities(db)

    configure_transfer(
        repository,
        inventory,
        destination,
    )

    with pytest.raises(HTTPException) as error:
        service.transfer(
            db,
            1,
            InventoryTransferCreate(
                sucursal_destino_id=21,
                cantidad=16,
            ),
        )

    assert error.value.status_code == 409

    repository.update_quantity.assert_not_called()
    repository.create_movement.assert_not_called()

    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_transfer_rolls_back_if_second_movement_fails(
    service,
    db,
    repository,
    inventory,
    destination,
):
    configure_active_entities(db)

    configure_transfer(
        repository,
        inventory,
        destination,
    )

    repository.create_movement.side_effect = [
        MagicMock(),
        RuntimeError("failure"),
    ]

    with pytest.raises(RuntimeError):
        service.transfer(
            db,
            1,
            InventoryTransferCreate(
                sucursal_destino_id=21,
                cantidad=2,
            ),
        )

    db.rollback.assert_called_once()
    db.commit.assert_not_called()


# ============================================================
# HISTORIAL DE MOVIMIENTOS
# ============================================================


def test_get_movements(
    service,
    db,
    repository,
    inventory,
):
    repository.get_by_id.return_value = inventory

    movement = InventoryMovement(
        id=3,
        inventario_id=1,
        tipo="ENTRADA",
        cantidad=5,
        motivo="Reposicion",
        referencia_tipo=None,
        referencia_id=None,
        usuario_id=7,
        created_at=datetime.now(timezone.utc),
    )

    repository.get_movements.return_value = [movement]

    result = service.get_movements(
        db,
        1,
        limit=10,
        offset=5,
    )

    assert result.total == 1
    assert (
        result.movimientos[0].tipo
        == MovementType.ENTRADA
    )

    repository.get_movements.assert_called_once_with(
        db,
        inventario_id=1,
        limit=10,
        offset=5,
    )
