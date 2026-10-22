
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.branch import (
    BranchCreate,
    BranchListResponse,
    BranchResponse,
    BranchUpdate,
)


@pytest.fixture
def valid_branch_data():
    return {
        "nombre": "Sucursal Centro",
        "codigo": "SUC-001",
        "direccion": "Calle 60, Centro",
        "ciudad": "Mérida",
        "estado": "Yucatán",
        "codigo_postal": "97000",
        "telefono": "9991234567",
        "latitud": Decimal("20.9674"),
        "longitud": Decimal("-89.6237"),
    }


@pytest.fixture
def branch_response(valid_branch_data):
    now = datetime.now(timezone.utc)
    return BranchResponse(
        id=1,
        **valid_branch_data,
        activo=True,
        created_at=now,
        updated_at=now,
    )


def test_create_valid_branch(valid_branch_data):
    branch = BranchCreate(**valid_branch_data)

    assert branch.nombre == "Sucursal Centro"
    assert branch.codigo == "SUC-001"
    assert branch.ciudad == "Mérida"
    assert branch.estado == "Yucatán"
    assert branch.telefono == "9991234567"


def test_create_branch_without_optional_fields(valid_branch_data):
    for field in (
        "telefono",
        "codigo_postal",
        "latitud",
        "longitud",
    ):
        valid_branch_data.pop(field)

    branch = BranchCreate(**valid_branch_data)

    assert branch.telefono is None
    assert branch.codigo_postal is None
    assert branch.latitud is None
    assert branch.longitud is None


def test_normalize_branch_code(valid_branch_data):
    valid_branch_data["codigo"] = "suc-001"

    branch = BranchCreate(**valid_branch_data)

    assert branch.codigo == "SUC-001"


def test_strip_whitespace(valid_branch_data):
    valid_branch_data["nombre"] = "  Sucursal Centro  "
    valid_branch_data["codigo"] = "  suc-001  "
    valid_branch_data["ciudad"] = "  Mérida  "

    branch = BranchCreate(**valid_branch_data)

    assert branch.nombre == "Sucursal Centro"
    assert branch.codigo == "SUC-001"
    assert branch.ciudad == "Mérida"


@pytest.mark.parametrize(
    "field",
    ["nombre", "codigo", "direccion", "ciudad", "estado"],
)
def test_reject_missing_required_fields(valid_branch_data, field):
    valid_branch_data.pop(field)

    with pytest.raises(ValidationError):
        BranchCreate(**valid_branch_data)


@pytest.mark.parametrize(
    "field",
    ["nombre", "codigo", "direccion", "ciudad", "estado"],
)
def test_reject_empty_required_fields(valid_branch_data, field):
    valid_branch_data[field] = ""

    with pytest.raises(ValidationError):
        BranchCreate(**valid_branch_data)


@pytest.mark.parametrize(
    ("field", "max_length"),
    [
        ("nombre", 100),
        ("codigo", 30),
        ("direccion", 255),
        ("ciudad", 100),
        ("estado", 100),
        ("codigo_postal", 10),
        ("telefono", 20),
    ],
)
def test_reject_long_fields(valid_branch_data, field, max_length):
    valid_branch_data[field] = "A" * (max_length + 1)

    with pytest.raises(ValidationError):
        BranchCreate(**valid_branch_data)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("latitud", Decimal("90.01")),
        ("latitud", Decimal("-90.01")),
        ("longitud", Decimal("180.01")),
        ("longitud", Decimal("-180.01")),
    ],
)
def test_reject_invalid_coordinates(valid_branch_data, field, value):
    valid_branch_data[field] = value

    with pytest.raises(ValidationError):
        BranchCreate(**valid_branch_data)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("latitud", Decimal("90")),
        ("latitud", Decimal("-90")),
        ("longitud", Decimal("180")),
        ("longitud", Decimal("-180")),
    ],
)
def test_accept_coordinate_boundaries(valid_branch_data, field, value):
    valid_branch_data[field] = value

    branch = BranchCreate(**valid_branch_data)

    assert getattr(branch, field) == value


def test_reject_extra_fields(valid_branch_data):
    valid_branch_data["activo"] = False

    with pytest.raises(ValidationError):
        BranchCreate(**valid_branch_data)


def test_reject_manual_creation_timestamps(valid_branch_data):
    valid_branch_data["created_at"] = datetime.now(timezone.utc)

    with pytest.raises(ValidationError):
        BranchCreate(**valid_branch_data)


def test_update_partial_branch():
    branch = BranchUpdate(nombre="Sucursal Norte")

    assert branch.model_dump(exclude_unset=True) == {
        "nombre": "Sucursal Norte",
    }


def test_update_city_and_state():
    branch = BranchUpdate(
        ciudad="Campeche",
        estado="Campeche",
    )

    assert branch.ciudad == "Campeche"
    assert branch.estado == "Campeche"


def test_update_normalizes_code():
    branch = BranchUpdate(codigo="suc-002")

    assert branch.codigo == "SUC-002"


def test_update_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        BranchUpdate(activo=False)


def test_update_rejects_empty_name():
    with pytest.raises(ValidationError):
        BranchUpdate(nombre="")


def test_update_rejects_invalid_latitude():
    with pytest.raises(ValidationError):
        BranchUpdate(latitud=Decimal("91"))


def test_response_schema(branch_response):
    assert branch_response.id == 1
    assert branch_response.activo is True
    assert branch_response.codigo == "SUC-001"
    assert branch_response.ciudad == "Mérida"
    assert branch_response.created_at is not None
    assert branch_response.updated_at is not None


def test_response_serializes_coordinates(branch_response):
    data = branch_response.model_dump(mode="json")

    assert data["latitud"] == "20.9674"
    assert data["longitud"] == "-89.6237"


def test_list_response(branch_response):
    result = BranchListResponse(
        total=1,
        sucursales=[branch_response],
    )

    assert result.total == 1
    assert len(result.sucursales) == 1
    assert result.sucursales[0].id == 1


def test_reject_negative_total():
    with pytest.raises(ValidationError):
        BranchListResponse(total=-1, sucursales=[])


def test_reject_invalid_response_id(valid_branch_data):
    now = datetime.now(timezone.utc)

    with pytest.raises(ValidationError):
        BranchResponse(
            id="invalid",
            **valid_branch_data,
            activo=True,
            created_at=now,
            updated_at=now,
        )


def test_reject_missing_response_timestamps(valid_branch_data):
    with pytest.raises(ValidationError):
        BranchResponse(
            id=1,
            **valid_branch_data,
            activo=True,
        )
