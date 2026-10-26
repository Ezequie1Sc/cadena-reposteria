"""Pruebas del repositorio de empleados."""

import pytest

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.modules.branches.model import Branch
from app.modules.employees.model import Employee
from app.modules.employees.repository import EmployeeRepository
from app.modules.employees.schemas import EmployeeCreate, EmployeeUpdate
from app.shared.models.user_reference import users_reference


@pytest.fixture
def db():
    """Crear una base SQLite temporal para cada prueba."""

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

    with SessionLocal() as session:
        yield session

    engine.dispose()


@pytest.fixture
def repository():
    return EmployeeRepository()


@pytest.fixture
def employee_data():
    return EmployeeCreate(
        usuario_id=1,
        sucursal_id=1,
        numero_empleado="EMP-001",
        puesto="Cajero",
    )


@pytest.fixture
def references(db: Session):
    """Registrar las referencias necesarias para las claves foráneas."""

    db.execute(
        users_reference.insert().values(id=1)
    )

    db.execute(
        users_reference.insert().values(id=2)
    )

    branch = Branch(
        nombre="Sucursal Centro",
        codigo="CENTRO",
        direccion="Calle Principal 123",
        ciudad="Mérida",
        estado="Yucatán",
    )

    db.add(branch)
    db.flush()

    return branch


def test_create_employee(
    db,
    repository,
    references,
    employee_data,
):
    employee = repository.create(db, employee_data)

    assert employee.id is not None
    assert employee.usuario_id == 1
    assert employee.numero_empleado == "EMP-001"
    assert employee.activo is True


def test_get_employee_by_id(
    db,
    repository,
    references,
    employee_data,
):
    employee = repository.create(db, employee_data)

    result = repository.get_by_id(db, employee.id)

    assert result is not None
    assert result.id == employee.id


def test_get_nonexistent_employee(
    db,
    repository,
):
    result = repository.get_by_id(db, 999)

    assert result is None


def test_get_employee_by_number(
    db,
    repository,
    references,
    employee_data,
):
    repository.create(db, employee_data)

    result = repository.get_by_employee_number(
        db,
        "emp-001",
    )

    assert result is not None
    assert result.numero_empleado == "EMP-001"


def test_get_employee_by_user_id(
    db,
    repository,
    references,
    employee_data,
):
    repository.create(db, employee_data)

    result = repository.get_by_user_id(db, 1)

    assert result is not None
    assert result.usuario_id == 1


def test_get_all_employees(
    db,
    repository,
    references,
    employee_data,
):
    repository.create(db, employee_data)

    employees = repository.get_all(db)

    assert len(employees) == 1


def test_filter_employees_by_branch(
    db,
    repository,
    references,
    employee_data,
):
    repository.create(db, employee_data)

    employees = repository.get_all(
        db,
        sucursal_id=references.id,
    )

    assert len(employees) == 1


def test_search_employee_by_number(
    db,
    repository,
    references,
    employee_data,
):
    repository.create(db, employee_data)

    employees = repository.get_all(
        db,
        busqueda="EMP-001",
    )

    assert len(employees) == 1


def test_search_employee_by_position(
    db,
    repository,
    references,
    employee_data,
):
    repository.create(db, employee_data)

    employees = repository.get_all(
        db,
        busqueda="Cajero",
    )

    assert len(employees) == 1


def test_update_employee(
    db,
    repository,
    references,
    employee_data,
):
    employee = repository.create(db, employee_data)

    updated = repository.update(
        db,
        employee,
        EmployeeUpdate(puesto="Supervisor"),
    )

    assert updated.puesto == "Supervisor"


def test_deactivate_employee(
    db,
    repository,
    references,
    employee_data,
):
    employee = repository.create(db, employee_data)

    deactivated = repository.deactivate(
        db,
        employee,
    )

    assert deactivated.activo is False


def test_reactivate_employee(
    db,
    repository,
    references,
    employee_data,
):
    employee = repository.create(db, employee_data)

    repository.deactivate(db, employee)

    reactivated = repository.reactivate(
        db,
        employee,
    )

    assert reactivated.activo is True


def test_inactive_employees_are_excluded(
    db,
    repository,
    references,
    employee_data,
):
    employee = repository.create(db, employee_data)

    repository.deactivate(db, employee)

    employees = repository.get_all(db)

    assert employees == []


def test_include_inactive_employees(
    db,
    repository,
    references,
    employee_data,
):
    employee = repository.create(db, employee_data)

    repository.deactivate(db, employee)

    employees = repository.get_all(
        db,
        solo_activos=False,
    )

    assert len(employees) == 1
    assert employees[0].activo is False