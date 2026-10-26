"""Pruebas de la lógica de negocio del módulo de empleados."""

import pytest

from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.modules.branches.model import Branch
from app.modules.employees.model import Employee
from app.modules.employees.schemas import EmployeeCreate, EmployeeUpdate
from app.modules.employees.service import EmployeeService
from app.shared.models.user_reference import users_reference
from app.shared.models.role_reference import roles_reference
from tests.employees.fixtures import create_test_users


@pytest.fixture
def db():
    """Base SQLite aislada para cada prueba."""

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(
        engine,
        tables=[
            roles_reference,
            users_reference,
            Branch.__table__,
            Employee.__table__,
        ],
    )

    SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )

    try:
        with SessionLocal() as session:
            yield session
    finally:
        engine.dispose()


@pytest.fixture
def service():
    return EmployeeService()


@pytest.fixture
def references(db):
    """Crear usuarios y sucursales de prueba."""

    create_test_users(db, (1, 2, 3))

    branch = Branch(
        nombre="Sucursal Centro",
        codigo="CENTRO",
        direccion="Calle Principal 123",
        ciudad="Mérida",
        estado="Yucatán",
    )

    db.add(branch)
    db.commit()
    db.refresh(branch)

    return branch


@pytest.fixture
def employee_data(references):
    return EmployeeCreate(
        usuario_id=1,
        sucursal_id=references.id,
        numero_empleado="EMP-001",
        puesto="Cajero",
    )


@pytest.fixture
def created_employee(db, service, employee_data):
    return service.create_employee(db, employee_data)


def assert_http_error(exc_info, status_code):
    assert exc_info.value.status_code == status_code


def test_create_employee(db, service, employee_data):
    employee = service.create_employee(db, employee_data)

    assert employee.id > 0
    assert employee.usuario_id == 1
    assert employee.numero_empleado == "EMP-001"
    assert employee.puesto == "Cajero"
    assert employee.activo is True


def test_create_employee_persists_data(db, service, employee_data):
    employee = service.create_employee(db, employee_data)

    stored = db.get(Employee, employee.id)

    assert stored is not None
    assert stored.numero_empleado == "EMP-001"


def test_create_employee_with_nonexistent_user(db, service, references):
    data = EmployeeCreate(
        usuario_id=999,
        sucursal_id=references.id,
        numero_empleado="EMP-999",
        puesto="Cajero",
    )

    with pytest.raises(HTTPException) as exc:
        service.create_employee(db, data)

    assert_http_error(exc, 422)


def test_create_employee_with_nonexistent_branch(db, service, references):
    data = EmployeeCreate(
        usuario_id=1,
        sucursal_id=999,
        numero_empleado="EMP-001",
        puesto="Cajero",
    )

    with pytest.raises(HTTPException) as exc:
        service.create_employee(db, data)

    assert_http_error(exc, 422)


def test_create_employee_with_inactive_branch(db, service, references):
    references.activo = False
    db.commit()

    data = EmployeeCreate(
        usuario_id=1,
        sucursal_id=references.id,
        numero_empleado="EMP-001",
        puesto="Cajero",
    )

    with pytest.raises(HTTPException) as exc:
        service.create_employee(db, data)

    assert_http_error(exc, 422)


def test_create_employee_with_duplicate_number(
    db, service, references, created_employee
):
    data = EmployeeCreate(
        usuario_id=2,
        sucursal_id=references.id,
        numero_empleado="emp-001",
        puesto="Supervisor",
    )

    with pytest.raises(HTTPException) as exc:
        service.create_employee(db, data)

    assert_http_error(exc, 409)


def test_create_employee_with_duplicate_user(
    db, service, references, created_employee
):
    data = EmployeeCreate(
        usuario_id=1,
        sucursal_id=references.id,
        numero_empleado="EMP-002",
        puesto="Supervisor",
    )

    with pytest.raises(HTTPException) as exc:
        service.create_employee(db, data)

    assert_http_error(exc, 409)


def test_get_employees(db, service, created_employee):
    employees = service.get_employees(db)

    assert len(employees) == 1
    assert employees[0].id == created_employee.id


def test_get_employee_by_id(db, service, created_employee):
    employee = service.get_employee_by_id(
        db,
        created_employee.id,
    )

    assert employee is not None
    assert employee.id == created_employee.id


def test_get_nonexistent_employee(db, service):
    employee = service.get_employee_by_id(db, 999)

    assert employee is None


def test_update_employee_position(db, service, created_employee):
    employee = service.update_employee(
        db,
        created_employee.id,
        EmployeeUpdate(puesto="Supervisor"),
    )

    assert employee.puesto == "Supervisor"


def test_update_employee_number(db, service, created_employee):
    employee = service.update_employee(
        db,
        created_employee.id,
        EmployeeUpdate(numero_empleado="emp-010"),
    )

    assert employee.numero_empleado == "EMP-010"


def test_update_employee_user(db, service, created_employee):
    employee = service.update_employee(
        db,
        created_employee.id,
        EmployeeUpdate(usuario_id=2),
    )

    assert employee.usuario_id == 2


def test_update_employee_nonexistent(db, service):
    with pytest.raises(HTTPException) as exc:
        service.update_employee(
            db,
            999,
            EmployeeUpdate(puesto="Supervisor"),
        )

    assert_http_error(exc, 404)


@pytest.mark.parametrize(
    "field",
    ["usuario_id", "sucursal_id", "numero_empleado", "puesto"],
)
def test_update_rejects_null_required_fields(
    db, service, created_employee, field
):
    with pytest.raises(HTTPException) as exc:
        service.update_employee(
            db,
            created_employee.id,
            EmployeeUpdate(**{field: None}),
        )

    assert_http_error(exc, 422)


def test_update_rejects_nonexistent_user(db, service, created_employee):
    with pytest.raises(HTTPException) as exc:
        service.update_employee(
            db,
            created_employee.id,
            EmployeeUpdate(usuario_id=999),
        )

    assert_http_error(exc, 422)


def test_update_rejects_nonexistent_branch(db, service, created_employee):
    with pytest.raises(HTTPException) as exc:
        service.update_employee(
            db,
            created_employee.id,
            EmployeeUpdate(sucursal_id=999),
        )

    assert_http_error(exc, 422)


def test_update_rejects_inactive_branch(
    db, service, references, created_employee
):
    references.activo = False
    db.commit()

    with pytest.raises(HTTPException) as exc:
        service.update_employee(
            db,
            created_employee.id,
            EmployeeUpdate(sucursal_id=references.id),
        )

    assert_http_error(exc, 422)


def test_update_rejects_duplicate_number(
    db, service, references, created_employee
):
    second = service.create_employee(
        db,
        EmployeeCreate(
            usuario_id=2,
            sucursal_id=references.id,
            numero_empleado="EMP-002",
            puesto="Supervisor",
        ),
    )

    with pytest.raises(HTTPException) as exc:
        service.update_employee(
            db,
            second.id,
            EmployeeUpdate(numero_empleado="EMP-001"),
        )

    assert_http_error(exc, 409)


def test_update_rejects_duplicate_user(
    db, service, references, created_employee
):
    second = service.create_employee(
        db,
        EmployeeCreate(
            usuario_id=2,
            sucursal_id=references.id,
            numero_empleado="EMP-002",
            puesto="Supervisor",
        ),
    )

    with pytest.raises(HTTPException) as exc:
        service.update_employee(
            db,
            second.id,
            EmployeeUpdate(usuario_id=1),
        )

    assert_http_error(exc, 409)


def test_deactivate_employee(db, service, created_employee):
    result = service.deactivate_employee(
        db,
        created_employee.id,
    )

    assert result.activo is False

    stored = db.get(Employee, created_employee.id)
    assert stored is not None
    assert stored.activo is False


def test_deactivate_employee_is_idempotent(db, service, created_employee):
    service.deactivate_employee(db, created_employee.id)

    result = service.deactivate_employee(
        db,
        created_employee.id,
    )

    assert result.activo is False


def test_deactivate_nonexistent_employee(db, service):
    with pytest.raises(HTTPException) as exc:
        service.deactivate_employee(db, 999)

    assert_http_error(exc, 404)


def test_reactivate_employee(db, service, created_employee):
    service.deactivate_employee(db, created_employee.id)

    result = service.reactivate_employee(
        db,
        created_employee.id,
    )

    assert result.activo is True


def test_reactivate_employee_is_idempotent(db, service, created_employee):
    result = service.reactivate_employee(
        db,
        created_employee.id,
    )

    assert result.activo is True


def test_reactivate_nonexistent_employee(db, service):
    with pytest.raises(HTTPException) as exc:
        service.reactivate_employee(db, 999)

    assert_http_error(exc, 404)


def test_reactivate_rejects_inactive_branch(
    db, service, references, created_employee
):
    service.deactivate_employee(db, created_employee.id)

    references.activo = False
    db.commit()

    with pytest.raises(HTTPException) as exc:
        service.reactivate_employee(
            db,
            created_employee.id,
        )

    assert_http_error(exc, 422)


def test_inactive_employees_excluded_from_default_list(
    db, service, created_employee
):
    service.deactivate_employee(db, created_employee.id)

    employees = service.get_employees(db)

    assert employees == []


def test_inactive_employees_can_be_listed(
    db, service, created_employee
):
    service.deactivate_employee(db, created_employee.id)

    employees = service.get_employees(
        db,
        solo_activos=False,
    )

    assert len(employees) == 1
    assert employees[0].activo is False


def test_filter_employees_by_branch(
    db, service, references, created_employee
):
    employees = service.get_employees(
        db,
        sucursal_id=references.id,
    )

    assert len(employees) == 1


def test_search_employees_by_position(db, service, created_employee):
    employees = service.get_employees(
        db,
        busqueda="Cajero",
    )

    assert len(employees) == 1