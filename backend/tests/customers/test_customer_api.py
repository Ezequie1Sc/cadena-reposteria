
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.main import app
from app.modules.customers.routes import get_customer_service
from app.modules.customers.service import (
    CustomerConflictError,
    CustomerNotFoundError,
    CustomerValidationError,
)


CUSTOMER_DATA = {
    "id": 1,
    "usuario_id": None,
    "nombre": "María",
    "apellido": "López",
    "email": "maria@example.com",
    "telefono": "9991234567",
    "fecha_nacimiento": "1998-05-15",
    "activo": True,
    "created_at": datetime(
        2026, 10, 23, tzinfo=timezone.utc
    ).isoformat(),
}


@pytest.fixture
def mock_service():
    service = MagicMock()

    app.dependency_overrides[get_customer_service] = (
        lambda: service
    )

    yield service

    app.dependency_overrides.pop(
        get_customer_service,
        None,
    )


@pytest.fixture
def client(mock_service):
    with TestClient(app) as test_client:
        yield test_client


# ============================================================
# LISTAR CLIENTES
# ============================================================

def test_list_customers(client, mock_service):
    mock_service.get_all.return_value = {
        "items": [CUSTOMER_DATA],
        "total": 1,
        "page": 1,
        "page_size": 20,
    }

    response = client.get("/clientes")

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["activo"] is True

    mock_service.get_all.assert_called_once_with(
        page=1,
        page_size=20,
        solo_activos=None,
    )


def test_list_customers_with_pagination(
    client,
    mock_service,
):
    mock_service.get_all.return_value = {
        "items": [],
        "total": 0,
        "page": 2,
        "page_size": 5,
    }

    response = client.get(
        "/clientes",
        params={"page": 2, "page_size": 5},
    )

    assert response.status_code == 200
    assert response.json()["page"] == 2
    assert response.json()["page_size"] == 5

    mock_service.get_all.assert_called_once_with(
        page=2,
        page_size=5,
        solo_activos=None,
    )


def test_list_active_customers(client, mock_service):
    mock_service.get_all.return_value = {
        "items": [CUSTOMER_DATA],
        "total": 1,
        "page": 1,
        "page_size": 20,
    }

    response = client.get(
        "/clientes",
        params={"solo_activos": "true"},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["activo"] is True

    mock_service.get_all.assert_called_once_with(
        page=1,
        page_size=20,
        solo_activos=True,
    )


def test_list_inactive_customers(client, mock_service):
    inactive_customer = {
        **CUSTOMER_DATA,
        "activo": False,
    }

    mock_service.get_all.return_value = {
        "items": [inactive_customer],
        "total": 1,
        "page": 1,
        "page_size": 20,
    }

    response = client.get(
        "/clientes",
        params={"solo_activos": "false"},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["activo"] is False

    mock_service.get_all.assert_called_once_with(
        page=1,
        page_size=20,
        solo_activos=False,
    )


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page": -1},
        {"page_size": 0},
        {"page_size": 101},
        {"solo_activos": "invalido"},
    ],
)
def test_list_customers_invalid_parameters(
    client,
    mock_service,
    params,
):
    response = client.get(
        "/clientes",
        params=params,
    )

    assert response.status_code == 422
    mock_service.get_all.assert_not_called()


# ============================================================
# CONSULTAR CLIENTE
# ============================================================

def test_get_customer(client, mock_service):
    mock_service.get_by_id.return_value = CUSTOMER_DATA

    response = client.get("/clientes/1")

    assert response.status_code == 200
    assert response.json()["id"] == 1
    assert response.json()["nombre"] == "María"
    assert response.json()["activo"] is True

    mock_service.get_by_id.assert_called_once_with(1)


def test_get_inactive_customer(client, mock_service):
    mock_service.get_by_id.return_value = {
        **CUSTOMER_DATA,
        "activo": False,
    }

    response = client.get("/clientes/1")

    assert response.status_code == 200
    assert response.json()["activo"] is False

    mock_service.get_by_id.assert_called_once_with(1)


def test_get_customer_not_found(
    client,
    mock_service,
):
    mock_service.get_by_id.side_effect = (
        CustomerNotFoundError("Cliente no encontrado")
    )

    response = client.get("/clientes/999")

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Cliente no encontrado"
    )


def test_get_customer_invalid_id(
    client,
    mock_service,
):
    response = client.get("/clientes/0")

    assert response.status_code == 422
    mock_service.get_by_id.assert_not_called()


# ============================================================
# CREAR CLIENTE
# ============================================================

def test_create_customer(client, mock_service):
    mock_service.create.return_value = CUSTOMER_DATA

    payload = {
        "nombre": "María",
        "apellido": "López",
        "email": "maria@example.com",
        "telefono": "9991234567",
        "fecha_nacimiento": "1998-05-15",
    }

    response = client.post(
        "/clientes",
        json=payload,
    )

    assert response.status_code == 201
    assert response.json()["nombre"] == "María"
    assert response.json()["id"] == 1
    assert response.json()["activo"] is True

    mock_service.create.assert_called_once()


def test_create_customer_invalid_payload(
    client,
    mock_service,
):
    response = client.post(
        "/clientes",
        json={},
    )

    assert response.status_code == 422
    mock_service.create.assert_not_called()


def test_create_customer_conflict(
    client,
    mock_service,
):
    mock_service.create.side_effect = (
        CustomerConflictError(
            "El usuario ya está asociado a un cliente"
        )
    )

    response = client.post(
        "/clientes",
        json={"nombre": "María"},
    )

    assert response.status_code == 409


def test_create_customer_invalid_user(
    client,
    mock_service,
):
    mock_service.create.side_effect = (
        CustomerValidationError(
            "El usuario indicado no existe"
        )
    )

    response = client.post(
        "/clientes",
        json={
            "nombre": "María",
            "usuario_id": 999,
        },
    )

    assert response.status_code == 400


# ============================================================
# ACTUALIZAR CLIENTE
# ============================================================

def test_update_customer(client, mock_service):
    mock_service.update.return_value = {
        **CUSTOMER_DATA,
        "nombre": "Mariana",
    }

    response = client.patch(
        "/clientes/1",
        json={"nombre": "Mariana"},
    )

    assert response.status_code == 200
    assert response.json()["nombre"] == "Mariana"
    assert response.json()["activo"] is True

    mock_service.update.assert_called_once()


def test_update_customer_not_found(
    client,
    mock_service,
):
    mock_service.update.side_effect = (
        CustomerNotFoundError("Cliente no encontrado")
    )

    response = client.patch(
        "/clientes/999",
        json={"nombre": "Mariana"},
    )

    assert response.status_code == 404


def test_update_customer_conflict(
    client,
    mock_service,
):
    mock_service.update.side_effect = (
        CustomerConflictError(
            "El usuario ya está asociado a un cliente"
        )
    )

    response = client.patch(
        "/clientes/1",
        json={"usuario_id": 2},
    )

    assert response.status_code == 409


def test_update_customer_invalid_data(
    client,
    mock_service,
):
    response = client.patch(
        "/clientes/1",
        json={},
    )

    assert response.status_code == 422
    mock_service.update.assert_not_called()


def test_update_customer_null_name(
    client,
    mock_service,
):
    response = client.patch(
        "/clientes/1",
        json={"nombre": None},
    )

    assert response.status_code == 422
    mock_service.update.assert_not_called()


# ============================================================
# DESACTIVAR CLIENTE
# ============================================================

def test_deactivate_customer(client, mock_service):
    mock_service.deactivate.return_value = {
        **CUSTOMER_DATA,
        "activo": False,
    }

    response = client.delete("/clientes/1")

    assert response.status_code == 204
    assert response.content == b""

    mock_service.deactivate.assert_called_once_with(1)


def test_deactivate_customer_not_found(
    client,
    mock_service,
):
    mock_service.deactivate.side_effect = (
        CustomerNotFoundError("Cliente no encontrado")
    )

    response = client.delete("/clientes/999")

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Cliente no encontrado"
    )


def test_deactivate_already_inactive_customer(
    client,
    mock_service,
):
    mock_service.deactivate.side_effect = (
        CustomerConflictError(
            "El cliente ya se encuentra desactivado."
        )
    )

    response = client.delete("/clientes/1")

    assert response.status_code == 409
    assert "desactivado" in response.json()["detail"]


def test_deactivate_customer_invalid_id(
    client,
    mock_service,
):
    response = client.delete("/clientes/0")

    assert response.status_code == 422
    mock_service.deactivate.assert_not_called()


# ============================================================
# REACTIVAR CLIENTE
# ============================================================

def test_reactivate_customer(client, mock_service):
    mock_service.reactivate.return_value = {
        **CUSTOMER_DATA,
        "activo": True,
    }

    response = client.patch(
        "/clientes/1/reactivar"
    )

    assert response.status_code == 200
    assert response.json()["id"] == 1
    assert response.json()["activo"] is True

    mock_service.reactivate.assert_called_once_with(1)


def test_reactivate_customer_not_found(
    client,
    mock_service,
):
    mock_service.reactivate.side_effect = (
        CustomerNotFoundError("Cliente no encontrado")
    )

    response = client.patch(
        "/clientes/999/reactivar"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Cliente no encontrado"
    )


def test_reactivate_already_active_customer(
    client,
    mock_service,
):
    mock_service.reactivate.side_effect = (
        CustomerConflictError(
            "El cliente ya se encuentra activo."
        )
    )

    response = client.patch(
        "/clientes/1/reactivar"
    )

    assert response.status_code == 409
    assert "activo" in response.json()["detail"]


def test_reactivate_customer_invalid_id(
    client,
    mock_service,
):
    response = client.patch(
        "/clientes/0/reactivar"
    )

    assert response.status_code == 422
    mock_service.reactivate.assert_not_called()


# ============================================================
# ERRORES DE BASE DE DATOS (HTTP 503)
# ============================================================

@pytest.mark.parametrize(
    "method,path,payload,service_method",
    [
        ("get", "/clientes", None, "get_all"),
        ("get", "/clientes/1", None, "get_by_id"),
        (
            "post",
            "/clientes",
            {"nombre": "María"},
            "create",
        ),
        (
            "patch",
            "/clientes/1",
            {"nombre": "Mariana"},
            "update",
        ),
        (
            "delete",
            "/clientes/1",
            None,
            "deactivate",
        ),
        (
            "patch",
            "/clientes/1/reactivar",
            None,
            "reactivate",
        ),
    ],
)
def test_customer_database_error(
    client,
    mock_service,
    method,
    path,
    payload,
    service_method,
):
    getattr(
        mock_service,
        service_method,
    ).side_effect = OperationalError(
        "SELECT 1",
        {},
        Exception("Database unavailable"),
    )

    response = client.request(
        method.upper(),
        path,
        json=payload,
    )

    assert response.status_code == 503
    assert "detail" in response.json()
    assert response.json()["detail"]
