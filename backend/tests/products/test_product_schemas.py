
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.modules.products.schemas import ProductCreate, ProductUpdate


@pytest.fixture
def valid_product_data():
    """Datos válidos para las pruebas de productos."""
    return {
        "categoria_id": 1,
        "nombre": "Pastel de chocolate",
        "descripcion": "Pastel para celebraciones",
        "sku": "TEST-PASTEL-001",
        "precio": Decimal("450.00"),
        "imagen_url": None,
    }


def test_create_product_with_valid_data(valid_product_data):
    """Permite crear un esquema con datos válidos."""
    product = ProductCreate(**valid_product_data)

    assert product.nombre == "Pastel de chocolate"
    assert product.precio == Decimal("450.00")
    assert product.categoria_id == 1


def test_reject_negative_price(valid_product_data):
    """Rechaza precios negativos."""
    valid_product_data["precio"] = Decimal("-10.00")

    with pytest.raises(ValidationError):
        ProductCreate(**valid_product_data)


def test_allow_zero_price(valid_product_data):
    """Permite precio cero según las reglas actuales."""
    valid_product_data["precio"] = Decimal("0.00")

    product = ProductCreate(**valid_product_data)

    assert product.precio == Decimal("0.00")


def test_reject_invalid_category_id(valid_product_data):
    """Rechaza identificadores de categoría no positivos."""
    valid_product_data["categoria_id"] = 0

    with pytest.raises(ValidationError):
        ProductCreate(**valid_product_data)


def test_reject_long_sku(valid_product_data):
    """Rechaza SKU que superen los 50 caracteres."""
    valid_product_data["sku"] = "A" * 51

    with pytest.raises(ValidationError):
        ProductCreate(**valid_product_data)


def test_reject_unknown_create_field(valid_product_data):
    """Rechaza propiedades no definidas al crear productos."""
    valid_product_data["activo"] = False

    with pytest.raises(ValidationError) as exc_info:
        ProductCreate(**valid_product_data)

    assert any(
        error["type"] == "extra_forbidden"
        for error in exc_info.value.errors()
    )


def test_update_only_selected_fields():
    """Permite actualizar únicamente los campos enviados."""
    update = ProductUpdate(
        nombre="Pastel actualizado",
        precio=Decimal("500.00"),
    )

    changes = update.model_dump(exclude_unset=True)

    assert changes == {
        "nombre": "Pastel actualizado",
        "precio": Decimal("500.00"),
    }


def test_reject_unknown_update_field():
    """Impide modificar activo mediante ProductUpdate."""
    with pytest.raises(ValidationError) as exc_info:
        ProductUpdate(activo=False)

    assert any(
        error["type"] == "extra_forbidden"
        for error in exc_info.value.errors()
    )


def test_reject_negative_update_price():
    """Rechaza precios negativos durante una actualización."""
    with pytest.raises(ValidationError):
        ProductUpdate(precio=Decimal("-1.00"))


def test_allow_nullable_description():
    """Permite eliminar una descripción enviando null."""
    update = ProductUpdate(descripcion=None)

    assert update.model_dump(exclude_unset=True) == {
        "descripcion": None
    }
