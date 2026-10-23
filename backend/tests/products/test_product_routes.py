
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.modules.products.routes import router
from app.db.session import get_db
from app.modules.products.schemas import ProductResponse
from fastapi import FastAPI


@pytest.fixture
def product():
    now = datetime.now(timezone.utc)

    return ProductResponse(
        id=11,
        categoria_id=1,
        nombre="Pastel de chocolate",
        descripcion="Producto de prueba",
        sku="TEST-001",
        precio=Decimal("250.00"),
        imagen_url=None,
        activo=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def client():
    # Creamos una aplicación aislada para probar las rutas.
    app = FastAPI()
    app.include_router(router)

    # Sustituimos la sesión real por una simulada.
    fake_db = Mock()

    def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@patch("app.modules.products.routes.product_service")
def test_list_products(service, client, product):
    service.get_products.return_value = [product]

    response = client.get("/productos")

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["productos"][0]["id"] == 11


@patch("app.modules.products.routes.product_service")
def test_list_products_with_filters(service, client):
    service.get_products.return_value = []

    response = client.get(
        "/productos",
        params={
            "busqueda": "chocolate",
            "categoria_id": 1,
            "solo_activos": True,
        },
    )

    assert response.status_code == 200

    service.get_products.assert_called_once()
    assert service.get_products.call_args.kwargs["busqueda"] == "chocolate"
    assert service.get_products.call_args.kwargs["categoria_id"] == 1


@patch("app.modules.products.routes.product_service")
def test_get_product(service, client, product):
    service.get_product_by_id.return_value = product

    response = client.get("/productos/11")

    assert response.status_code == 200
    assert response.json()["id"] == 11


@patch("app.modules.products.routes.product_service")
def test_get_nonexistent_product(service, client):
    service.get_product_by_id.return_value = None

    response = client.get("/productos/99999")

    assert response.status_code == 404


@patch("app.modules.products.routes.product_service")
def test_create_product(service, client, product):
    service.create_product.return_value = product

    response = client.post(
        "/productos",
        json={
            "categoria_id": 1,
            "nombre": "Pastel de chocolate",
            "descripcion": "Producto de prueba",
            "sku": "TEST-001",
            "precio": 250.00,
            "imagen_url": None,
        },
    )

    assert response.status_code == 201
    assert response.json()["id"] == 11


@patch("app.modules.products.routes.product_service")
def test_reject_invalid_create_price(service, client):
    response = client.post(
        "/productos",
        json={
            "categoria_id": 1,
            "nombre": "Pastel de prueba",
            "sku": "TEST-002",
            "precio": -50,
        },
    )

    assert response.status_code == 422
    service.create_product.assert_not_called()


@patch("app.modules.products.routes.product_service")
def test_update_product(service, client, product):
    service.update_product.return_value = product

    response = client.patch(
        "/productos/11",
        json={"nombre": "Pastel actualizado"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == 11


@patch("app.modules.products.routes.product_service")
def test_reject_unknown_update_field(service, client):
    response = client.patch(
        "/productos/11",
        json={"activo": False},
    )

    assert response.status_code == 422
    service.update_product.assert_not_called()


@patch("app.modules.products.routes.product_service")
def test_deactivate_product(service, client, product):
    service.deactivate_product.return_value = product

    response = client.delete("/productos/11")

    assert response.status_code == 204
    assert response.content == b""
    service.deactivate_product.assert_called_once()


@patch("app.modules.products.routes.product_service")
def test_reactivate_product(service, client, product):
    service.reactivate_product.return_value = product

    response = client.patch("/productos/11/reactivar")

    assert response.status_code == 200
    assert response.json()["activo"] is True


@patch("app.modules.products.routes.product_service")
def test_duplicate_sku_response(service, client):
    service.create_product.side_effect = HTTPException(
        status_code=409,
        detail="Ya existe un producto con este SKU",
    )

    response = client.post(
        "/productos",
        json={
            "categoria_id": 1,
            "nombre": "Pastel duplicado",
            "sku": "TEST-001",
            "precio": 250.00,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Ya existe un producto con este SKU"
    )


@patch("app.modules.products.routes.product_service")
def test_database_error_returns_503(service, client):
    from sqlalchemy.exc import OperationalError

    service.get_products.side_effect = OperationalError(
        "SELECT",
        {},
        Exception("Database unavailable"),
    )

    response = client.get("/productos")

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "No fue posible consultar los productos"
    )
