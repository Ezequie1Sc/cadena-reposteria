
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.schemas.product import ProductCreate, ProductUpdate
from app.services.product_service import ProductService


@pytest.fixture
def service():
    return ProductService()


@pytest.fixture
def db():
    return Mock()


@pytest.fixture
def product_data():
    return ProductCreate(
        categoria_id=1,
        nombre="Pastel de chocolate",
        descripcion="Pastel de prueba",
        sku="TEST-001",
        precio=Decimal("250.00"),
        imagen_url=None,
    )


@pytest.fixture
def product():
    now = datetime.now(timezone.utc)

    return SimpleNamespace(
        id=11,
        categoria_id=1,
        nombre="Pastel de chocolate",
        descripcion="Pastel de prueba",
        sku="TEST-001",
        precio=Decimal("250.00"),
        imagen_url=None,
        activo=True,
        created_at=now,
        updated_at=now,
    )


def test_validate_existing_category(service, db):
    db.get.return_value = SimpleNamespace(
        id=1,
        activo=True,
    )

    service.validate_category(db, 1)

    db.get.assert_called_once()


def test_reject_nonexistent_category(service, db):
    db.get.return_value = None

    with pytest.raises(HTTPException) as exc:
        service.validate_category(db, 99999)

    assert exc.value.status_code == 422


def test_reject_inactive_category(service, db):
    db.get.return_value = SimpleNamespace(
        id=1,
        activo=False,
    )

    with pytest.raises(HTTPException) as exc:
        service.validate_category(db, 1)

    assert exc.value.status_code == 422


@patch("app.services.product_service.product_repository")
def test_reject_duplicate_sku(repository, service, db):
    repository.get_by_sku.return_value = SimpleNamespace(
        id=5,
        sku="TEST-001",
    )

    with pytest.raises(HTTPException) as exc:
        service.validate_sku(db, "TEST-001")

    assert exc.value.status_code == 409


@patch("app.services.product_service.product_repository")
def test_allow_available_sku(repository, service, db):
    repository.get_by_sku.return_value = None

    service.validate_sku(db, "TEST-001")

    repository.get_by_sku.assert_called_once_with(
        db,
        "TEST-001",
    )


@patch("app.services.product_service.product_repository")
def test_create_product(
    repository, service, db, product_data, product
):
    db.get.return_value = SimpleNamespace(activo=True)
    repository.get_by_sku.return_value = None
    repository.create.return_value = product

    result = service.create_product(db, product_data)

    assert result.id == 11
    assert result.nombre == "Pastel de chocolate"

    repository.create.assert_called_once_with(
        db,
        product_data,
    )
    db.commit.assert_called_once()


@patch("app.services.product_service.product_repository")
def test_create_product_integrity_error(
    repository, service, db, product_data
):
    db.get.return_value = SimpleNamespace(activo=True)
    repository.get_by_sku.return_value = None
    repository.create.side_effect = IntegrityError(
        "INSERT",
        {},
        Exception("Duplicate key"),
    )

    with pytest.raises(HTTPException) as exc:
        service.create_product(db, product_data)

    assert exc.value.status_code == 409
    db.rollback.assert_called_once()
    db.commit.assert_not_called()


@patch("app.services.product_service.product_repository")
def test_get_nonexistent_product(repository, service, db):
    repository.get_by_id.return_value = None

    result = service.get_product_by_id(db, 99999)

    assert result is None


@patch("app.services.product_service.product_repository")
def test_update_nonexistent_product(repository, service, db):
    repository.get_by_id.return_value = None

    with pytest.raises(HTTPException) as exc:
        service.update_product(
            db,
            99999,
            ProductUpdate(nombre="Nuevo nombre"),
        )

    assert exc.value.status_code == 404
    db.commit.assert_not_called()


@patch("app.services.product_service.product_repository")
def test_reject_null_required_field(
    repository, service, db, product
):
    repository.get_by_id.return_value = product

    with pytest.raises(HTTPException) as exc:
        service.update_product(
            db,
            11,
            ProductUpdate(nombre=None),
        )

    assert exc.value.status_code == 422
    repository.update.assert_not_called()
    db.commit.assert_not_called()


@patch("app.services.product_service.product_repository")
def test_update_product(repository, service, db, product):
    repository.get_by_id.return_value = product

    updated_product = SimpleNamespace(
        **vars(product)
    )
    updated_product.nombre = "Pastel actualizado"
    updated_product.precio = Decimal("300.00")

    repository.update.return_value = updated_product

    changes = ProductUpdate(
        nombre="Pastel actualizado",
        precio=Decimal("300.00"),
    )

    result = service.update_product(db, 11, changes)

    assert result.nombre == "Pastel actualizado"
    assert result.precio == Decimal("300.00")
    db.commit.assert_called_once()


@patch("app.services.product_service.product_repository")
def test_deactivate_product(repository, service, db, product):
    repository.get_by_id.return_value = product

    product.activo = False
    repository.deactivate.return_value = product

    # Simulamos un producto activo al consultarlo.
    repository.get_by_id.return_value = SimpleNamespace(
        **{**vars(product), "activo": True}
    )

    result = service.deactivate_product(db, 11)

    assert result.activo is False
    repository.deactivate.assert_called_once()
    db.commit.assert_called_once()


@patch("app.services.product_service.product_repository")
def test_reactivate_product(repository, service, db, product):
    product.activo = False
    repository.get_by_id.return_value = product

    db.get.return_value = SimpleNamespace(activo=True)

    reactivated = SimpleNamespace(
        **{**vars(product), "activo": True}
    )
    repository.reactivate.return_value = reactivated

    result = service.reactivate_product(db, 11)

    assert result.activo is True
    repository.reactivate.assert_called_once()
    db.commit.assert_called_once()


@patch("app.services.product_service.product_repository")
def test_reactivate_with_inactive_category(
    repository, service, db, product
):
    product.activo = False
    repository.get_by_id.return_value = product

    db.get.return_value = SimpleNamespace(activo=False)

    with pytest.raises(HTTPException) as exc:
        service.reactivate_product(db, 11)

    assert exc.value.status_code == 422
    repository.reactivate.assert_not_called()
    db.commit.assert_not_called()
