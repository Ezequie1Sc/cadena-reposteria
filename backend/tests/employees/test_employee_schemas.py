"""Pruebas de validación de los esquemas de empleados."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.modules.employees.schemas import (
    EmployeeCreate,
    EmployeeListResponse,
    EmployeeResponse,
    EmployeeUpdate,
)


def valid_employee_data() -> dict:
    return {
        "usuario_id": 1,
        "sucursal_id": 1,
        "numero_empleado": "emp-001",
        "puesto": "Cajero",
    }


def test_create_employee_valid():
    employee = EmployeeCreate(**valid_employee_data())

    assert employee.usuario_id == 1
    assert employee.sucursal_id == 1
    assert employee.numero_empleado == "EMP-001"
    assert employee.puesto == "Cajero"


def test_employee_number_is_normalized():
    employee = EmployeeCreate(
        usuario_id=1,
        sucursal_id=1,
        numero_empleado="  emp-002  ",
        puesto="Cajero",
    )

    assert employee.numero_empleado == "EMP-002"


@pytest.mark.parametrize(
    "field",
    ["usuario_id", "sucursal_id"],
)
def test_reject_non_positive_ids(field):
    data = valid_employee_data()
    data[field] = 0

    with pytest.raises(ValidationError):
        EmployeeCreate(**data)


@pytest.mark.parametrize(
    "field",
    ["numero_empleado", "puesto"],
)
def test_reject_empty_required_strings(field):
    data = valid_employee_data()
    data[field] = "   "

    with pytest.raises(ValidationError):
        EmployeeCreate(**data)


def test_reject_employee_number_over_max_length():
    data = valid_employee_data()
    data["numero_empleado"] = "X" * 31

    with pytest.raises(ValidationError):
        EmployeeCreate(**data)


def test_reject_position_over_max_length():
    data = valid_employee_data()
    data["puesto"] = "X" * 101

    with pytest.raises(ValidationError):
        EmployeeCreate(**data)


def test_reject_unknown_fields():
    data = valid_employee_data()
    data["salario"] = 10000

    with pytest.raises(ValidationError):
        EmployeeCreate(**data)


def test_partial_update():
    employee = EmployeeUpdate(puesto="Supervisor")

    assert employee.model_dump(exclude_unset=True) == {
        "puesto": "Supervisor"
    }


def test_update_employee_number_normalized():
    employee = EmployeeUpdate(numero_empleado="emp-003")

    assert employee.numero_empleado == "EMP-003"


def test_update_rejects_invalid_id():
    with pytest.raises(ValidationError):
        EmployeeUpdate(sucursal_id=-1)


def test_update_does_not_allow_active_field():
    with pytest.raises(ValidationError):
        EmployeeUpdate(activo=False)


def test_employee_response():
    employee = EmployeeResponse(
        **valid_employee_data(),
        id=10,
        activo=True,
        created_at=datetime.now(timezone.utc),
    )

    assert employee.id == 10
    assert employee.activo is True
    assert employee.numero_empleado == "EMP-001"


def test_employee_list_response():
    response = EmployeeListResponse(
        total=0,
        empleados=[],
    )

    assert response.total == 0
    assert response.empleados == []


def test_employee_list_rejects_negative_total():
    with pytest.raises(ValidationError):
        EmployeeListResponse(total=-1, empleados=[])