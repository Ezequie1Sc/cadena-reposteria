
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.modules.branches.model import Branch
from app.modules.branches.repository import BranchRepository
from app.modules.branches.schemas import BranchCreate, BranchUpdate


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(
        engine,
        tables=[Branch.__table__],
    )

    with Session(engine) as session:
        yield session

    engine.dispose()


@pytest.fixture
def repository():
    return BranchRepository()


def create_branch(
    db,
    nombre="Sucursal Centro",
    codigo="SUC-001",
    activo=True,
):
    branch = Branch(
        nombre=nombre,
        codigo=codigo,
        direccion="Calle 60, Centro",
        ciudad="Mérida",
        estado="Yucatán",
        codigo_postal="97000",
        telefono=None,
        latitud=Decimal("20.9674"),
        longitud=Decimal("-89.6237"),
        activo=activo,
    )

    db.add(branch)
    db.flush()
    db.refresh(branch)

    return branch


def test_create_branch(db, repository):
    data = BranchCreate(
        nombre="Sucursal Norte",
        codigo="SUC-002",
        direccion="Calle 50",
        ciudad="Mérida",
        estado="Yucatán",
    )

    branch = repository.create(db, data)

    assert branch.id is not None
    assert branch.nombre == "Sucursal Norte"
    assert branch.codigo == "SUC-002"
    assert branch.ciudad == "Mérida"
    assert branch.activo is True


def test_create_branch_with_coordinates(db, repository):
    data = BranchCreate(
        nombre="Sucursal Norte",
        codigo="SUC-002",
        direccion="Calle 50",
        ciudad="Mérida",
        estado="Yucatán",
        latitud=Decimal("20.9800"),
        longitud=Decimal("-89.6100"),
    )

    branch = repository.create(db, data)

    assert branch.latitud == Decimal("20.9800")
    assert branch.longitud == Decimal("-89.6100")


def test_create_branch_generates_timestamps(db, repository):
    branch = create_branch(db)

    assert branch.created_at is not None
    assert branch.updated_at is not None


def test_get_branch_by_id(db, repository):
    branch = create_branch(db)

    result = repository.get_by_id(db, branch.id)

    assert result is not None
    assert result.nombre == "Sucursal Centro"


def test_get_nonexistent_branch(db, repository):
    assert repository.get_by_id(db, 999) is None


def test_get_branch_by_code(db, repository):
    create_branch(db)

    result = repository.get_by_code(db, "SUC-001")

    assert result is not None
    assert result.nombre == "Sucursal Centro"


def test_get_branch_by_code_case_insensitive(db, repository):
    create_branch(db)

    result = repository.get_by_code(db, "suc-001")

    assert result is not None
    assert result.codigo == "SUC-001"


def test_get_nonexistent_code(db, repository):
    assert repository.get_by_code(db, "SUC-999") is None


def test_get_all_only_active(db, repository):
    create_branch(db)
    create_branch(
        db,
        nombre="Sucursal Sur",
        codigo="SUC-002",
        activo=False,
    )

    results = repository.get_all(db)

    assert len(results) == 1
    assert results[0].nombre == "Sucursal Centro"


def test_get_all_including_inactive(db, repository):
    create_branch(db)
    create_branch(
        db,
        nombre="Sucursal Sur",
        codigo="SUC-002",
        activo=False,
    )

    results = repository.get_all(
        db,
        solo_activos=False,
    )

    assert len(results) == 2


def test_get_all_search_by_name(db, repository):
    create_branch(db)
    create_branch(
        db,
        nombre="Sucursal Norte",
        codigo="SUC-002",
    )

    results = repository.get_all(
        db,
        busqueda="norte",
    )

    assert len(results) == 1
    assert results[0].codigo == "SUC-002"


def test_get_all_search_by_code(db, repository):
    create_branch(db)
    create_branch(
        db,
        nombre="Sucursal Norte",
        codigo="SUC-002",
    )

    results = repository.get_all(
        db,
        busqueda="suc-002",
    )

    assert len(results) == 1
    assert results[0].nombre == "Sucursal Norte"


def test_get_all_ordered_by_name(db, repository):
    create_branch(
        db,
        nombre="Sucursal Z",
        codigo="SUC-001",
    )
    create_branch(
        db,
        nombre="Sucursal A",
        codigo="SUC-002",
    )

    results = repository.get_all(db)

    assert [branch.nombre for branch in results] == [
        "Sucursal A",
        "Sucursal Z",
    ]


def test_update_branch(db, repository):
    branch = create_branch(db)

    data = BranchUpdate(
        nombre="Sucursal Centro Premium",
    )

    updated = repository.update(db, branch, data)

    assert updated.nombre == "Sucursal Centro Premium"


def test_update_branch_code(db, repository):
    branch = create_branch(db)

    updated = repository.update(
        db,
        branch,
        BranchUpdate(codigo="suc-010"),
    )

    assert updated.codigo == "SUC-010"


def test_update_branch_location(db, repository):
    branch = create_branch(db)

    updated = repository.update(
        db,
        branch,
        BranchUpdate(
            direccion="Avenida Central",
            ciudad="Campeche",
            estado="Campeche",
            codigo_postal="24000",
        ),
    )

    assert updated.direccion == "Avenida Central"
    assert updated.ciudad == "Campeche"
    assert updated.estado == "Campeche"
    assert updated.codigo_postal == "24000"


def test_update_branch_coordinates(db, repository):
    branch = create_branch(db)

    updated = repository.update(
        db,
        branch,
        BranchUpdate(
            latitud=Decimal("19.8450"),
            longitud=Decimal("-90.5230"),
        ),
    )

    assert updated.latitud == Decimal("19.8450")
    assert updated.longitud == Decimal("-90.5230")


def test_deactivate_branch(db, repository):
    branch = create_branch(db)

    updated = repository.deactivate(db, branch)

    assert updated.activo is False


def test_reactivate_branch(db, repository):
    branch = create_branch(db, activo=False)

    updated = repository.reactivate(db, branch)

    assert updated.activo is True


def test_create_duplicate_code_raises_error(db, repository):
    create_branch(db)

    data = BranchCreate(
        nombre="Otra sucursal",
        codigo="SUC-001",
        direccion="Calle Principal",
        ciudad="Campeche",
        estado="Campeche",
    )

    with pytest.raises(IntegrityError):
        repository.create(db, data)

    db.rollback()


def test_updated_at_changes_after_update(db, repository):
    """
    Verifica que SQLAlchemy actualice automáticamente
    updated_at cuando se modifica una sucursal.
    """

    branch = create_branch(db)

    # Establecer una fecha anterior para comprobar el cambio.
    old_timestamp = datetime.now(timezone.utc) - timedelta(days=1)

    db.execute(
        update(Branch)
        .where(Branch.id == branch.id)
        .values(updated_at=old_timestamp)
    )

    db.flush()
    db.refresh(branch)

    previous_timestamp = branch.updated_at

    # Actualizar mediante el repositorio.
    repository.update(
        db,
        branch,
        BranchUpdate(
            nombre="Sucursal Centro Actualizada",
        ),
    )

    db.flush()
    db.refresh(branch)

    assert branch.nombre == "Sucursal Centro Actualizada"
    assert branch.updated_at > previous_timestamp
