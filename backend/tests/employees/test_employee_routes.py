"""Pruebas HTTP de los endpoints de empleados."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.modules.employees.schemas import EmployeeResponse


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def employee():
    return EmployeeResponse(
        id=1,
        usuario_id=10,
        sucursal_id=1,
        numero_empleado="EMP-001",
        puesto="Cajero",
        activo=True,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def employee_payload():
    return {
        "usuario_id": 10,
        "sucursal_id": 1,
        "numero_empleado": "EMP-001",
        "puesto": "Cajero",
    }


def test_list_employees(client, employee):
    with patch(
        "app.modules.employees.routes.employee_service.get_employees",
        return_value=[employee],
    ):
        response = client.get("/empleados")

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["empleados"][0]["id"] == 1


def test_list_employees_with_filters(client):
    with patch(
        "app.modules.employees.routes.employee_service.get_employees",
        return_value=[],
    ) as mocked:
        response = client.get(
            "/empleados",
            params={
                "busqueda": "Cajero",
                "sucursal_id": 1,
                "solo_activos": "false",
            },
        )

    assert response.status_code == 200
    assert response.json() == {"total": 0, "empleados": []}

    mocked.assert_called_once()
    assert mocked.call_args.kwargs["busqueda"] == "Cajero"
    assert mocked.call_args.kwargs["sucursal_id"] == 1
    assert mocked.call_args.kwargs["solo_activos"] is False


def test_list_rejects_invalid_branch_id(client):
    response = client.get(
        "/empleados",
        params={"sucursal_id": -1},
    )

    assert response.status_code == 422


def test_get_employee(client, employee):
    with patch(
        "app.modules.employees.routes.employee_service.get_employee_by_id",
        return_value=employee,
    ):
        response = client.get("/empleados/1")

    assert response.status_code == 200
    assert response.json()["numero_empleado"] == "EMP-001"


def test_get_nonexistent_employee(client):
    with patch(
        "app.modules.employees.routes.employee_service.get_employee_by_id",
        return_value=None,
    ):
        response = client.get("/empleados/999")

    assert response.status_code == 404


def test_create_employee(client, employee, employee_payload):
    with patch(
        "app.modules.employees.routes.employee_service.create_employee",
        return_value=employee,
    ):
        response = client.post(
            "/empleados",
            json=employee_payload,
        )

    assert response.status_code == 201
    assert response.json()["id"] == 1


def test_create_rejects_invalid_payload(client, employee_payload):
    employee_payload["usuario_id"] = -1

    response = client.post(
        "/empleados",
        json=employee_payload,
    )

    assert response.status_code == 422


def test_create_rejects_unknown_fields(client, employee_payload):
    employee_payload["salario"] = 10000

    response = client.post(
        "/empleados",
        json=employee_payload,
    )

    assert response.status_code == 422


def test_create_duplicate_employee(client, employee_payload):
    with patch(
        "app.modules.employees.routes.employee_service.create_employee",
        side_effect=HTTPException(
            status_code=409,
            detail="Ya existe un empleado con este número",
        ),
    ):
        response = client.post(
            "/empleados",
            json=employee_payload,
        )

    assert response.status_code == 409


def test_update_employee(client, employee):
    updated = employee.model_copy(
        update={"puesto": "Supervisor"},
    )

    with patch(
        "app.modules.employees.routes.employee_service.update_employee",
        return_value=updated,
    ):
        response = client.patch(
            "/empleados/1",
            json={"puesto": "Supervisor"},
        )

    assert response.status_code == 200
    assert response.json()["puesto"] == "Supervisor"


def test_update_nonexistent_employee(client):
    with patch(
        "app.modules.employees.routes.employee_service.update_employee",
        side_effect=HTTPException(
            status_code=404,
            detail="Empleado no encontrado",
        ),
    ):
        response = client.patch(
            "/empleados/999",
            json={"puesto": "Supervisor"},
        )

    assert response.status_code == 404


def test_update_rejects_unknown_fields(client):
    response = client.patch(
        "/empleados/1",
        json={"activo": False},
    )

    assert response.status_code == 422


def test_deactivate_employee(client, employee):
    with patch(
        "app.modules.employees.routes.employee_service.deactivate_employee",
        return_value=employee,
    ):
        response = client.delete("/empleados/1")

    assert response.status_code == 204
    assert response.content == b""


def test_deactivate_nonexistent_employee(client):
    with patch(
        "app.modules.employees.routes.employee_service.deactivate_employee",
        side_effect=HTTPException(
            status_code=404,
            detail="Empleado no encontrado",
        ),
    ):
        response = client.delete("/empleados/999")

    assert response.status_code == 404


def test_reactivate_employee(client, employee):
    with patch(
        "app.modules.employees.routes.employee_service.reactivate_employee",
        return_value=employee,
    ):
        response = client.patch(
            "/empleados/1/reactivar",
        )

    assert response.status_code == 200
    assert response.json()["activo"] is True


def test_reactivate_nonexistent_employee(client):
    with patch(
        "app.modules.employees.routes.employee_service.reactivate_employee",
        side_effect=HTTPException(
            status_code=404,
            detail="Empleado no encontrado",
        ),
    ):
        response = client.patch(
            "/empleados/999/reactivar",
        )

    assert response.status_code == 404