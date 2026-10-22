
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api.routes.branches import router
from app.db.session import get_db
from app.schemas.branch import BranchResponse


@pytest.fixture
def branch():
    now = datetime.now(timezone.utc)

    return BranchResponse(
        id=11,
        nombre="Sucursal Centro",
        codigo="SUC-001",
        direccion="Calle 60, Centro",
        ciudad="Mérida",
        estado="Yucatán",
        codigo_postal="97000",
        telefono=None,
        latitud=None,
        longitud=None,
        activo=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def valid_payload():
    return {
        "nombre": "Sucursal Centro",
        "codigo": "suc-001",
        "direccion": "Calle 60, Centro",
        "ciudad": "Mérida",
        "estado": "Yucatán",
    }


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)

    fake_db = Mock()

    def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@patch("app.api.routes.branches.branch_service")
def test_list_branches(service, client, branch):
    service.get_branches.return_value = [branch]

    response = client.get("/sucursales")

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["sucursales"][0]["id"] == 11


@patch("app.api.routes.branches.branch_service")
def test_list_branches_with_filters(service, client):
    service.get_branches.return_value = []

    response = client.get(
        "/sucursales",
        params={
            "busqueda": "centro",
            "solo_activos": False,
        },
    )

    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert (
        service.get_branches.call_args.kwargs["busqueda"]
        == "centro"
    )
    assert (
        service.get_branches.call_args.kwargs["solo_activos"]
        is False
    )


@patch("app.api.routes.branches.branch_service")
def test_get_branch(service, client, branch):
    service.get_branch_by_id.return_value = branch

    response = client.get("/sucursales/11")

    assert response.status_code == 200
    assert response.json()["id"] == 11
    assert response.json()["codigo"] == "SUC-001"
    assert response.json()["ciudad"] == "Mérida"
    assert response.json()["estado"] == "Yucatán"
    assert response.json()["created_at"] is not None


@patch("app.api.routes.branches.branch_service")
def test_get_nonexistent_branch(service, client):
    service.get_branch_by_id.return_value = None

    response = client.get("/sucursales/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Sucursal no encontrada"


@patch("app.api.routes.branches.branch_service")
def test_create_branch(service, client, branch, valid_payload):
    service.create_branch.return_value = branch

    response = client.post(
        "/sucursales",
        json=valid_payload,
    )

    assert response.status_code == 201
    assert response.json()["id"] == 11

    service.create_branch.assert_called_once()
    data = service.create_branch.call_args.kwargs["data"]

    assert data.codigo == "SUC-001"
    assert data.ciudad == "Mérida"
    assert data.estado == "Yucatán"


@patch("app.api.routes.branches.branch_service")
def test_reject_invalid_create_name(
    service, client, valid_payload
):
    valid_payload["nombre"] = ""

    response = client.post(
        "/sucursales",
        json=valid_payload,
    )

    assert response.status_code == 422
    service.create_branch.assert_not_called()


@patch("app.api.routes.branches.branch_service")
def test_reject_missing_code(
    service, client, valid_payload
):
    valid_payload.pop("codigo")

    response = client.post(
        "/sucursales",
        json=valid_payload,
    )

    assert response.status_code == 422
    service.create_branch.assert_not_called()


@pytest.mark.parametrize("field", ["ciudad", "estado"])
@patch("app.api.routes.branches.branch_service")
def test_reject_missing_location(
    service, client, valid_payload, field
):
    valid_payload.pop(field)

    response = client.post(
        "/sucursales",
        json=valid_payload,
    )

    assert response.status_code == 422
    service.create_branch.assert_not_called()


@patch("app.api.routes.branches.branch_service")
def test_reject_invalid_coordinates(
    service, client, valid_payload
):
    valid_payload["latitud"] = 95

    response = client.post(
        "/sucursales",
        json=valid_payload,
    )

    assert response.status_code == 422
    service.create_branch.assert_not_called()


@patch("app.api.routes.branches.branch_service")
def test_update_branch(service, client, branch):
    service.update_branch.return_value = branch

    response = client.patch(
        "/sucursales/11",
        json={"nombre": "Sucursal Centro"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == 11
    service.update_branch.assert_called_once()


@patch("app.api.routes.branches.branch_service")
def test_update_location(service, client, branch):
    service.update_branch.return_value = branch

    response = client.patch(
        "/sucursales/11",
        json={
            "ciudad": "Campeche",
            "estado": "Campeche",
        },
    )

    assert response.status_code == 200

    data = service.update_branch.call_args.kwargs["data"]
    assert data.ciudad == "Campeche"
    assert data.estado == "Campeche"


@patch("app.api.routes.branches.branch_service")
def test_reject_unknown_update_field(service, client):
    response = client.patch(
        "/sucursales/11",
        json={"activo": False},
    )

    assert response.status_code == 422
    service.update_branch.assert_not_called()


@patch("app.api.routes.branches.branch_service")
def test_deactivate_branch(service, client, branch):
    service.deactivate_branch.return_value = branch

    response = client.delete("/sucursales/11")

    assert response.status_code == 204
    assert response.content == b""
    service.deactivate_branch.assert_called_once()


@patch("app.api.routes.branches.branch_service")
def test_reactivate_branch(service, client, branch):
    service.reactivate_branch.return_value = branch

    response = client.patch("/sucursales/11/reactivar")

    assert response.status_code == 200
    assert response.json()["activo"] is True
    service.reactivate_branch.assert_called_once()


@patch("app.api.routes.branches.branch_service")
def test_duplicate_branch_code_response(
    service, client, valid_payload
):
    service.create_branch.side_effect = HTTPException(
        status_code=409,
        detail="Ya existe una sucursal con este código",
    )

    response = client.post(
        "/sucursales",
        json=valid_payload,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Ya existe una sucursal con este código"
    )


@patch("app.api.routes.branches.branch_service")
def test_database_error_returns_503(service, client):
    service.get_branches.side_effect = OperationalError(
        "SELECT",
        {},
        Exception("Database unavailable"),
    )

    response = client.get("/sucursales")

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "No fue posible consultar las sucursales"
    )


@patch("app.api.routes.branches.branch_service")
def test_database_error_on_create_rolls_back(
    service, client, valid_payload
):
    service.create_branch.side_effect = OperationalError(
        "INSERT",
        {},
        Exception("Database unavailable"),
    )

    response = client.post(
        "/sucursales",
        json=valid_payload,
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "No fue posible crear la sucursal"
    )


@patch("app.api.routes.branches.branch_service")
def test_reject_invalid_branch_id(service, client):
    response = client.get("/sucursales/0")

    assert response.status_code == 422
    service.get_branch_by_id.assert_not_called()


@patch("app.api.routes.branches.branch_service")
def test_reject_invalid_search(service, client):
    response = client.get(
        "/sucursales",
        params={"busqueda": "x" * 121},
    )

    assert response.status_code == 422
    service.get_branches.assert_not_called()
