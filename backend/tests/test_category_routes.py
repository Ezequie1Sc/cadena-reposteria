
from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api.routes.categories import router
from app.db.session import get_db
from app.schemas.category import CategoryResponse


@pytest.fixture
def category():
    return CategoryResponse(
        id=11,
        nombre="Pasteles",
        descripcion="Categoría de pasteles",
        activo=True,
    )


@pytest.fixture
def client():
    # Aplicación aislada para probar las rutas.
    app = FastAPI()
    app.include_router(router)

    # Sustituir la sesión real por una simulada.
    fake_db = Mock()

    def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@patch("app.api.routes.categories.category_service")
def test_list_categories(service, client, category):
    service.get_categories.return_value = [category]

    response = client.get("/categorias")

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["categorias"][0]["id"] == 11


@patch("app.api.routes.categories.category_service")
def test_list_categories_with_filters(service, client):
    service.get_categories.return_value = []

    response = client.get(
        "/categorias",
        params={
            "busqueda": "pasteles",
            "solo_activos": False,
        },
    )

    assert response.status_code == 200
    assert response.json()["total"] == 0

    service.get_categories.assert_called_once()
    assert service.get_categories.call_args.kwargs["busqueda"] == "pasteles"
    assert service.get_categories.call_args.kwargs["solo_activos"] is False


@patch("app.api.routes.categories.category_service")
def test_get_category(service, client, category):
    service.get_category_by_id.return_value = category

    response = client.get("/categorias/11")

    assert response.status_code == 200
    assert response.json()["id"] == 11
    assert response.json()["nombre"] == "Pasteles"


@patch("app.api.routes.categories.category_service")
def test_get_nonexistent_category(service, client):
    service.get_category_by_id.return_value = None

    response = client.get("/categorias/99999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Categoría no encontrada"


@patch("app.api.routes.categories.category_service")
def test_create_category(service, client, category):
    service.create_category.return_value = category

    response = client.post(
        "/categorias",
        json={
            "nombre": "Pasteles",
            "descripcion": "Categoría de pasteles",
        },
    )

    assert response.status_code == 201
    assert response.json()["id"] == 11
    assert response.json()["nombre"] == "Pasteles"

    service.create_category.assert_called_once()


@patch("app.api.routes.categories.category_service")
def test_reject_invalid_create_name(service, client):
    response = client.post(
        "/categorias",
        json={
            "nombre": "",
            "descripcion": "Categoría inválida",
        },
    )

    assert response.status_code == 422
    service.create_category.assert_not_called()


@patch("app.api.routes.categories.category_service")
def test_update_category(service, client, category):
    service.update_category.return_value = category

    response = client.patch(
        "/categorias/11",
        json={"descripcion": "Nueva descripción"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == 11

    service.update_category.assert_called_once()


@patch("app.api.routes.categories.category_service")
def test_reject_unknown_update_field(service, client):
    response = client.patch(
        "/categorias/11",
        json={"activo": False},
    )

    assert response.status_code == 422
    service.update_category.assert_not_called()


@patch("app.api.routes.categories.category_service")
def test_deactivate_category(service, client, category):
    service.deactivate_category.return_value = category

    response = client.delete("/categorias/11")

    assert response.status_code == 204
    assert response.content == b""

    service.deactivate_category.assert_called_once()


@patch("app.api.routes.categories.category_service")
def test_reactivate_category(service, client, category):
    service.reactivate_category.return_value = category

    response = client.patch("/categorias/11/reactivar")

    assert response.status_code == 200
    assert response.json()["activo"] is True

    service.reactivate_category.assert_called_once()


@patch("app.api.routes.categories.category_service")
def test_duplicate_category_name_response(service, client):
    service.create_category.side_effect = HTTPException(
        status_code=409,
        detail="Ya existe una categoría con este nombre",
    )

    response = client.post(
        "/categorias",
        json={
            "nombre": "Pasteles",
            "descripcion": "Categoría duplicada",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Ya existe una categoría con este nombre"
    )


@patch("app.api.routes.categories.category_service")
def test_cannot_deactivate_category_with_active_products(
    service,
    client,
):
    service.deactivate_category.side_effect = HTTPException(
        status_code=409,
        detail="No se puede desactivar una categoría con productos activos",
    )

    response = client.delete("/categorias/11")

    assert response.status_code == 409
    assert "productos activos" in response.json()["detail"]


@patch("app.api.routes.categories.category_service")
def test_database_error_returns_503(service, client):
    service.get_categories.side_effect = OperationalError(
        "SELECT",
        {},
        Exception("Database unavailable"),
    )

    response = client.get("/categorias")

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "No fue posible consultar las categorías"
    )


@patch("app.api.routes.categories.category_service")
def test_database_error_on_create_rolls_back(service, client):
    service.create_category.side_effect = OperationalError(
        "INSERT",
        {},
        Exception("Database unavailable"),
    )

    response = client.post(
        "/categorias",
        json={"nombre": "Pasteles"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "No fue posible crear la categoría"
    )


@patch("app.api.routes.categories.category_service")
def test_reject_invalid_category_id(service, client):
    response = client.get("/categorias/0")

    assert response.status_code == 422
    service.get_category_by_id.assert_not_called()
