
from datetime import datetime, timezone

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.models.branch import Branch
from app.schemas.branch import BranchCreate, BranchUpdate
from app.services.branch_service import BranchService


@pytest.fixture
def service():
    return BranchService()


@pytest.fixture
def db():
    return MagicMock()


@pytest.fixture
def branch():
    now = datetime.now(timezone.utc)

    return Branch(
        id=1,
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
def repository():
    with patch(
        "app.services.branch_service.branch_repository"
    ) as mock:
        yield mock


@pytest.fixture
def create_data():
    return BranchCreate(
        nombre="Sucursal Centro",
        codigo="SUC-001",
        direccion="Calle 60, Centro",
        ciudad="Mérida",
        estado="Yucatán",
    )


def test_get_branches(service, db, branch, repository):
    repository.get_all.return_value = [branch]

    result = service.get_branches(db)

    assert len(result) == 1
    assert result[0].codigo == "SUC-001"
    repository.get_all.assert_called_once_with(
        db=db,
        busqueda=None,
        solo_activos=True,
    )


def test_get_branches_with_filters(
    service, db, branch, repository
):
    repository.get_all.return_value = [branch]

    result = service.get_branches(
        db,
        busqueda="centro",
        solo_activos=False,
    )

    assert len(result) == 1
    repository.get_all.assert_called_once_with(
        db=db,
        busqueda="centro",
        solo_activos=False,
    )


def test_get_branch_by_id(service, db, branch, repository):
    repository.get_by_id.return_value = branch

    result = service.get_branch_by_id(db, 1)

    assert result is not None
    assert result.id == 1
    assert result.ciudad == "Mérida"


def test_get_nonexistent_branch(service, db, repository):
    repository.get_by_id.return_value = None

    assert service.get_branch_by_id(db, 999) is None


def test_reject_duplicate_code(
    service, db, branch, repository
):
    repository.get_by_code.return_value = branch

    with pytest.raises(HTTPException) as exc:
        service.validate_code(db, "SUC-001")

    assert exc.value.status_code == 409


def test_allow_available_code(service, db, repository):
    repository.get_by_code.return_value = None

    service.validate_code(db, "SUC-002")

    repository.get_by_code.assert_called_once_with(
        db, "SUC-002"
    )


def test_allow_same_code_on_update(
    service, db, branch, repository
):
    repository.get_by_code.return_value = branch

    service.validate_code(
        db,
        "SUC-001",
        exclude_branch_id=1,
    )


def test_create_branch(
    service, db, branch, repository, create_data
):
    repository.get_by_code.return_value = None
    repository.create.return_value = branch

    result = service.create_branch(db, create_data)

    assert result.id == 1
    assert result.ciudad == "Mérida"
    repository.create.assert_called_once_with(
        db, create_data
    )
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(branch)


def test_create_duplicate_code(
    service, db, branch, repository, create_data
):
    repository.get_by_code.return_value = branch

    with pytest.raises(HTTPException) as exc:
        service.create_branch(db, create_data)

    assert exc.value.status_code == 409
    repository.create.assert_not_called()


def test_create_integrity_error(
    service, db, repository, create_data
):
    repository.get_by_code.return_value = None
    repository.create.side_effect = IntegrityError(
        "INSERT", {}, Exception("Duplicate code")
    )

    with pytest.raises(HTTPException) as exc:
        service.create_branch(db, create_data)

    assert exc.value.status_code == 409
    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_update_nonexistent_branch(
    service, db, repository
):
    repository.get_by_id.return_value = None

    with pytest.raises(HTTPException) as exc:
        service.update_branch(
            db, 999, BranchUpdate(nombre="Nueva")
        )

    assert exc.value.status_code == 404


@pytest.mark.parametrize(
    "field",
    [
        "nombre",
        "codigo",
        "direccion",
        "ciudad",
        "estado",
    ],
)
def test_reject_null_required_fields(
    service, db, branch, repository, field
):
    repository.get_by_id.return_value = branch

    with pytest.raises(HTTPException) as exc:
        service.update_branch(
            db, 1, BranchUpdate(**{field: None})
        )

    assert exc.value.status_code == 422
    db.commit.assert_not_called()


def test_update_branch(service, db, branch, repository):
    repository.get_by_id.return_value = branch

    def update(db_session, obj, data):
        obj.nombre = data.nombre
        return obj

    repository.update.side_effect = update

    result = service.update_branch(
        db, 1, BranchUpdate(nombre="Sucursal Premium")
    )

    assert result.nombre == "Sucursal Premium"
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(branch)


def test_update_city_and_state(
    service, db, branch, repository
):
    repository.get_by_id.return_value = branch

    def update(db_session, obj, data):
        obj.ciudad = data.ciudad
        obj.estado = data.estado
        return obj

    repository.update.side_effect = update

    result = service.update_branch(
        db,
        1,
        BranchUpdate(
            ciudad="Campeche",
            estado="Campeche",
        ),
    )

    assert result.ciudad == "Campeche"
    assert result.estado == "Campeche"
    db.commit.assert_called_once()


def test_update_duplicate_code(
    service, db, branch, repository
):
    other = Branch(
        id=2,
        nombre="Sucursal Norte",
        codigo="SUC-002",
        direccion="Calle 50",
        ciudad="Mérida",
        estado="Yucatán",
        activo=True,
    )

    repository.get_by_id.return_value = branch
    repository.get_by_code.return_value = other

    with pytest.raises(HTTPException) as exc:
        service.update_branch(
            db, 1, BranchUpdate(codigo="SUC-002")
        )

    assert exc.value.status_code == 409
    repository.update.assert_not_called()


def test_update_integrity_error(
    service, db, branch, repository
):
    repository.get_by_id.return_value = branch
    repository.update.side_effect = IntegrityError(
        "UPDATE", {}, Exception("Conflict")
    )

    with pytest.raises(HTTPException) as exc:
        service.update_branch(
            db, 1, BranchUpdate(nombre="Nuevo nombre")
        )

    assert exc.value.status_code == 409
    db.rollback.assert_called_once()


def test_deactivate_nonexistent(
    service, db, repository
):
    repository.get_by_id.return_value = None

    with pytest.raises(HTTPException) as exc:
        service.deactivate_branch(db, 999)

    assert exc.value.status_code == 404


def test_deactivate_branch(
    service, db, branch, repository
):
    repository.get_by_id.return_value = branch

    def deactivate(db_session, obj):
        obj.activo = False
        return obj

    repository.deactivate.side_effect = deactivate

    result = service.deactivate_branch(db, 1)

    assert result.activo is False
    db.commit.assert_called_once()


def test_deactivate_already_inactive(
    service, db, branch, repository
):
    branch.activo = False
    repository.get_by_id.return_value = branch

    result = service.deactivate_branch(db, 1)

    assert result.activo is False
    repository.deactivate.assert_not_called()
    db.commit.assert_not_called()


def test_deactivate_integrity_error(
    service, db, branch, repository
):
    repository.get_by_id.return_value = branch
    repository.deactivate.side_effect = IntegrityError(
        "UPDATE", {}, Exception("Conflict")
    )

    with pytest.raises(HTTPException) as exc:
        service.deactivate_branch(db, 1)

    assert exc.value.status_code == 409
    db.rollback.assert_called_once()


def test_reactivate_nonexistent(
    service, db, repository
):
    repository.get_by_id.return_value = None

    with pytest.raises(HTTPException) as exc:
        service.reactivate_branch(db, 999)

    assert exc.value.status_code == 404


def test_reactivate_branch(
    service, db, branch, repository
):
    branch.activo = False
    repository.get_by_id.return_value = branch

    def reactivate(db_session, obj):
        obj.activo = True
        return obj

    repository.reactivate.side_effect = reactivate

    result = service.reactivate_branch(db, 1)

    assert result.activo is True
    db.commit.assert_called_once()


def test_reactivate_already_active(
    service, db, branch, repository
):
    repository.get_by_id.return_value = branch

    result = service.reactivate_branch(db, 1)

    assert result.activo is True
    repository.reactivate.assert_not_called()
    db.commit.assert_not_called()


def test_reactivate_integrity_error(
    service, db, branch, repository
):
    branch.activo = False
    repository.get_by_id.return_value = branch
    repository.reactivate.side_effect = IntegrityError(
        "UPDATE", {}, Exception("Conflict")
    )

    with pytest.raises(HTTPException) as exc:
        service.reactivate_branch(db, 1)

    assert exc.value.status_code == 409
    db.rollback.assert_called_once()
