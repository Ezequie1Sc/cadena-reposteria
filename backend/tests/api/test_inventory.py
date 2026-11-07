
"""Pruebas HTTP de los endpoints de inventarios."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.jwt import create_access_token
from app.core.security import hash_password
from app.db.session import Base, get_db
from app.main import app
from app.modules.users.model import User
from app.shared.models.role_reference import roles_reference


PASSWORD = "PasswordSegura2026!"
BASE_URL = "/inventarios"


# ============================================================
# DATOS DE PRUEBA
# ============================================================


def inventory_data(
    inventory_id=1,
    branch_id=20,
    quantity=15,
):
    """Construye una respuesta válida de inventario."""

    return {
        "id": inventory_id,
        "producto_id": 10,
        "sucursal_id": branch_id,
        "cantidad": quantity,
        "stock_minimo": 5,
        "updated_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }


def movement_data():
    """Construye una respuesta válida de movimiento."""

    return {
        "id": 1,
        "inventario_id": 1,
        "tipo": "ENTRADA",
        "cantidad": 5,
        "motivo": "Reposicion",
        "referencia_tipo": None,
        "referencia_id": None,
        "usuario_id": 1,
        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }


def endpoint_cases():
    """Devuelve las nueve operaciones HTTP del módulo."""

    return [
        ("GET", BASE_URL, None),
        ("GET", f"{BASE_URL}/1", None),
        (
            "POST",
            BASE_URL,
            {
                "producto_id": 10,
                "sucursal_id": 20,
            },
        ),
        (
            "PATCH",
            f"{BASE_URL}/1",
            {"stock_minimo": 8},
        ),
        (
            "POST",
            f"{BASE_URL}/1/entradas",
            {"cantidad": 5},
        ),
        (
            "POST",
            f"{BASE_URL}/1/salidas",
            {"cantidad": 3},
        ),
        (
            "POST",
            f"{BASE_URL}/1/ajustes",
            {
                "cantidad_final": 20,
                "motivo": "Conteo",
            },
        ),
        (
            "POST",
            f"{BASE_URL}/1/traspasos",
            {
                "sucursal_destino_id": 21,
                "cantidad": 4,
            },
        ),
        (
            "GET",
            f"{BASE_URL}/1/movimientos",
            None,
        ),
    ]


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def db():
    """Crea una base SQLite independiente por prueba."""

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute(
            "PRAGMA foreign_keys=ON"
        )

    Base.metadata.create_all(
        engine,
        tables=[
            roles_reference,
            User.__table__,
        ],
    )

    with engine.begin() as connection:
        connection.exec_driver_sql(
            "ALTER TABLE roles "
            "ADD COLUMN activo BOOLEAN NOT NULL DEFAULT 1"
        )

        connection.execute(
            text(
                "INSERT INTO roles (id, activo) VALUES "
                "(1, 1), (2, 1), (3, 1)"
            )
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
def users(db):
    """Crea un administrador, empleado y cliente."""

    records = {}

    for role_id, name in (
        (1, "Administrador"),
        (2, "Empleado"),
        (3, "Cliente"),
    ):
        user = User(
            rol_id=role_id,
            nombre=name,
            apellido="Prueba",
            email=f"inventory{role_id}@example.com",
            password_hash=hash_password(PASSWORD),
            activo=True,
        )

        db.add(user)
        db.flush()

        records[role_id] = user

    db.commit()

    for user in records.values():
        db.refresh(user)

    return records


@pytest.fixture
def client(db):
    """Sustituye la conexión real por SQLite."""

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def service_mock():
    """Sustituye el servicio de inventarios por un mock."""

    with patch(
        "app.modules.inventory.routes.inventory_service"
    ) as mock:

        mock.get_all.return_value = {
            "total": 1,
            "inventarios": [
                inventory_data(),
            ],
        }

        mock.get_by_id.return_value = inventory_data()

        mock.create.return_value = inventory_data()

        mock.update_minimum_stock.return_value = (
            inventory_data()
        )

        mock.register_entry.return_value = (
            inventory_data(quantity=20)
        )

        mock.register_exit.return_value = (
            inventory_data(quantity=12)
        )

        mock.adjust_stock.return_value = (
            inventory_data(quantity=20)
        )

        mock.transfer.return_value = {
            "origen": inventory_data(
                inventory_id=1,
                branch_id=20,
                quantity=11,
            ),
            "destino": inventory_data(
                inventory_id=2,
                branch_id=21,
                quantity=9,
            ),
        }

        mock.get_movements.return_value = {
            "total": 1,
            "movimientos": [
                movement_data(),
            ],
        }

        yield mock


def auth_headers(user):
    """Genera un JWT válido para el usuario."""

    token = create_access_token(user.id)

    return {
        "Authorization": f"Bearer {token}",
    }


# ============================================================
# AUTENTICACIÓN
# ============================================================


@pytest.mark.parametrize(
    "method,path,payload",
    endpoint_cases(),
)
def test_inventory_routes_require_authentication(
    client,
    method,
    path,
    payload,
):
    """Los endpoints requieren autenticación."""

    response = client.request(
        method,
        path,
        json=payload,
    )

    assert response.status_code == 401


def test_invalid_token_returns_401(client):
    """Un JWT inválido debe ser rechazado."""

    response = client.get(
        BASE_URL,
        headers={
            "Authorization": "Bearer token-invalido",
        },
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    "method,path,payload",
    endpoint_cases(),
)
def test_customer_cannot_access_inventory(
    client,
    users,
    method,
    path,
    payload,
):
    """Los clientes no pueden administrar inventarios."""

    response = client.request(
        method,
        path,
        headers=auth_headers(users[3]),
        json=payload,
    )

    assert response.status_code == 403


@pytest.mark.parametrize(
    "method,path,payload",
    [
        (
            "POST",
            BASE_URL,
            {
                "producto_id": 10,
                "sucursal_id": 20,
            },
        ),
        (
            "PATCH",
            f"{BASE_URL}/1",
            {"stock_minimo": 8},
        ),
        (
            "POST",
            f"{BASE_URL}/1/ajustes",
            {
                "cantidad_final": 20,
                "motivo": "Conteo",
            },
        ),
        (
            "POST",
            f"{BASE_URL}/1/traspasos",
            {
                "sucursal_destino_id": 21,
                "cantidad": 4,
            },
        ),
    ],
)
def test_employee_cannot_perform_admin_operations(
    client,
    users,
    method,
    path,
    payload,
):
    """Los empleados no pueden realizar operaciones administrativas."""

    response = client.request(
        method,
        path,
        headers=auth_headers(users[2]),
        json=payload,
    )

    assert response.status_code == 403


def test_inactive_user_returns_401(
    client,
    db,
    users,
):
    """Un usuario inactivo pierde el acceso."""

    employee = users[2]
    employee.activo = False
    db.commit()

    response = client.get(
        BASE_URL,
        headers=auth_headers(employee),
    )

    assert response.status_code == 401


def test_inactive_role_returns_403(
    client,
    db,
    users,
):
    """Un rol inactivo no autoriza operaciones."""

    db.execute(
        text(
            "UPDATE roles SET activo = 0 "
            "WHERE id = 2"
        )
    )
    db.commit()

    response = client.get(
        BASE_URL,
        headers=auth_headers(users[2]),
    )

    assert response.status_code == 403


# ============================================================
# CONSULTAS DE INVENTARIOS
# ============================================================


@pytest.mark.parametrize("role_id", [1, 2])
def test_staff_can_list_inventories(
    client,
    users,
    service_mock,
    role_id,
):
    """Administradores y empleados pueden consultar inventarios."""

    response = client.get(
        BASE_URL,
        headers=auth_headers(users[role_id]),
        params={
            "sucursal_id": 20,
            "producto_id": 10,
            "solo_bajo_stock": "true",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["total"] == 1
    assert len(body["inventarios"]) == 1
    assert body["inventarios"][0]["id"] == 1

    # Verificar que el servicio fue llamado una sola vez.
    service_mock.get_all.assert_called_once()

    # Comprobar los filtros enviados al servicio.
    kwargs = service_mock.get_all.call_args.kwargs

    assert kwargs["db"] is not None
    assert kwargs["sucursal_id"] == 20
    assert kwargs["producto_id"] == 10
    assert kwargs["solo_bajo_stock"] is True


@pytest.mark.parametrize("role_id", [1, 2])
def test_staff_can_get_inventory(
    client,
    users,
    service_mock,
    role_id,
):
    """Administradores y empleados pueden consultar un inventario."""

    response = client.get(
        f"{BASE_URL}/1",
        headers=auth_headers(users[role_id]),
    )

    assert response.status_code == 200
    assert response.json()["id"] == 1

    service_mock.get_by_id.assert_called_once()

    args = service_mock.get_by_id.call_args.args

    assert args[1] == 1


# ============================================================
# CREACIÓN Y ACTUALIZACIÓN
# ============================================================


def test_admin_can_create_inventory(
    client,
    users,
    service_mock,
):
    """El administrador puede crear inventarios."""

    response = client.post(
        BASE_URL,
        headers=auth_headers(users[1]),
        json={
            "producto_id": 10,
            "sucursal_id": 20,
            "stock_minimo": 5,
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert body["producto_id"] == 10
    assert body["sucursal_id"] == 20

    service_mock.create.assert_called_once()

    args = service_mock.create.call_args.args

    assert args[1].producto_id == 10
    assert args[1].sucursal_id == 20
    assert args[1].stock_minimo == 5


def test_admin_can_update_minimum_stock(
    client,
    users,
    service_mock,
):
    """El administrador puede modificar el stock mínimo."""

    response = client.patch(
        f"{BASE_URL}/1",
        headers=auth_headers(users[1]),
        json={
            "stock_minimo": 8,
        },
    )

    assert response.status_code == 200

    service_mock.update_minimum_stock.assert_called_once()

    args = (
        service_mock.update_minimum_stock
        .call_args.args
    )

    assert args[1] == 1
    assert args[2].stock_minimo == 8


# ============================================================
# ENTRADAS DE PRODUCTOS
# ============================================================


@pytest.mark.parametrize("role_id", [1, 2])
def test_staff_can_register_entry(
    client,
    users,
    service_mock,
    role_id,
):
    """Administradores y empleados pueden registrar entradas."""

    response = client.post(
        f"{BASE_URL}/1/entradas",
        headers=auth_headers(users[role_id]),
        json={
            "cantidad": 5,
            "motivo": "Reposicion",
        },
    )

    assert response.status_code == 200
    assert response.json()["cantidad"] == 20

    service_mock.register_entry.assert_called_once()

    args = service_mock.register_entry.call_args

    assert args.args[1] == 1
    assert args.args[2].cantidad == 5
    assert args.args[2].motivo == "Reposicion"
    assert args.kwargs["usuario_id"] == users[role_id].id


# ============================================================
# SALIDAS DE PRODUCTOS
# ============================================================


@pytest.mark.parametrize("role_id", [1, 2])
def test_staff_can_register_exit(
    client,
    users,
    service_mock,
    role_id,
):
    """Administradores y empleados pueden registrar salidas."""

    response = client.post(
        f"{BASE_URL}/1/salidas",
        headers=auth_headers(users[role_id]),
        json={
            "cantidad": 3,
            "motivo": "Merma",
        },
    )

    assert response.status_code == 200
    assert response.json()["cantidad"] == 12

    service_mock.register_exit.assert_called_once()

    args = service_mock.register_exit.call_args

    assert args.args[1] == 1
    assert args.args[2].cantidad == 3
    assert args.args[2].motivo == "Merma"
    assert args.kwargs["usuario_id"] == users[role_id].id


# ============================================================
# AJUSTES DE INVENTARIO
# ============================================================


def test_admin_can_adjust_inventory(
    client,
    users,
    service_mock,
):
    """El administrador puede ajustar las existencias."""

    response = client.post(
        f"{BASE_URL}/1/ajustes",
        headers=auth_headers(users[1]),
        json={
            "cantidad_final": 20,
            "motivo": "Conteo fisico",
        },
    )

    assert response.status_code == 200
    assert response.json()["cantidad"] == 20

    service_mock.adjust_stock.assert_called_once()

    args = service_mock.adjust_stock.call_args

    assert args.args[1] == 1
    assert args.args[2].cantidad_final == 20
    assert args.args[2].motivo == "Conteo fisico"
    assert args.kwargs["usuario_id"] == users[1].id


# ============================================================
# TRASPASOS ENTRE SUCURSALES
# ============================================================


def test_admin_can_transfer_inventory(
    client,
    users,
    service_mock,
):
    """El administrador puede traspasar productos."""

    response = client.post(
        f"{BASE_URL}/1/traspasos",
        headers=auth_headers(users[1]),
        json={
            "sucursal_destino_id": 21,
            "cantidad": 4,
            "motivo": "Reposicion",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["origen"]["id"] == 1
    assert body["destino"]["id"] == 2

    service_mock.transfer.assert_called_once()

    args = service_mock.transfer.call_args

    assert args.args[1] == 1
    assert args.args[2].sucursal_destino_id == 21
    assert args.args[2].cantidad == 4
    assert args.kwargs["usuario_id"] == users[1].id


# ============================================================
# HISTORIAL DE MOVIMIENTOS
# ============================================================


@pytest.mark.parametrize("role_id", [1, 2])
def test_staff_can_list_movements(
    client,
    users,
    service_mock,
    role_id,
):
    """Administradores y empleados pueden consultar movimientos."""

    response = client.get(
        f"{BASE_URL}/1/movimientos",
        headers=auth_headers(users[role_id]),
        params={
            "limit": 10,
            "offset": 5,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["total"] == 1
    assert body["movimientos"][0]["tipo"] == "ENTRADA"

    service_mock.get_movements.assert_called_once()

    args = service_mock.get_movements.call_args

    assert args.args[1] == 1
    assert args.kwargs["limit"] == 10
    assert args.kwargs["offset"] == 5


# ============================================================
# VALIDACIONES HTTP
# ============================================================


@pytest.mark.parametrize(
    "method,path,payload",
    [
        (
            "POST",
            BASE_URL,
            {
                "producto_id": 0,
                "sucursal_id": 20,
            },
        ),
        (
            "POST",
            BASE_URL,
            {
                "producto_id": 10,
                "sucursal_id": -1,
            },
        ),
        (
            "PATCH",
            f"{BASE_URL}/1",
            {
                "stock_minimo": -1,
            },
        ),
        (
            "POST",
            f"{BASE_URL}/1/entradas",
            {
                "cantidad": 0,
            },
        ),
        (
            "POST",
            f"{BASE_URL}/1/salidas",
            {
                "cantidad": -1,
            },
        ),
        (
            "POST",
            f"{BASE_URL}/1/ajustes",
            {
                "cantidad_final": -1,
                "motivo": "Conteo",
            },
        ),
        (
            "POST",
            f"{BASE_URL}/1/ajustes",
            {
                "cantidad_final": 5,
                "motivo": "",
            },
        ),
        (
            "POST",
            f"{BASE_URL}/1/traspasos",
            {
                "sucursal_destino_id": 0,
                "cantidad": 4,
            },
        ),
        (
            "POST",
            f"{BASE_URL}/1/traspasos",
            {
                "sucursal_destino_id": 21,
                "cantidad": 0,
            },
        ),
        (
            "GET",
            f"{BASE_URL}/0",
            None,
        ),
        (
            "GET",
            f"{BASE_URL}/1/movimientos?limit=0",
            None,
        ),
        (
            "GET",
            f"{BASE_URL}/1/movimientos?limit=101",
            None,
        ),
        (
            "GET",
            f"{BASE_URL}/1/movimientos?offset=-1",
            None,
        ),
        (
            "GET",
            f"{BASE_URL}?sucursal_id=0",
            None,
        ),
        (
            "GET",
            f"{BASE_URL}?producto_id=-1",
            None,
        ),
    ],
)
def test_invalid_inventory_requests_return_422(
    client,
    users,
    service_mock,
    method,
    path,
    payload,
):
    """Los datos fuera de rango deben devolver 422."""

    response = client.request(
        method,
        path,
        headers=auth_headers(users[1]),
        json=payload,
    )

    assert response.status_code == 422


# ============================================================
# ERRORES DE NEGOCIO
# ============================================================


def test_missing_inventory_returns_404(
    client,
    users,
    service_mock,
):
    """Un inventario inexistente devuelve 404."""

    service_mock.get_by_id.side_effect = HTTPException(
        status_code=404,
        detail="Inventario no encontrado",
    )

    response = client.get(
        f"{BASE_URL}/999",
        headers=auth_headers(users[1]),
    )

    assert response.status_code == 404


def test_business_conflict_returns_409(
    client,
    users,
    service_mock,
):
    """Un inventario duplicado devuelve 409."""

    service_mock.create.side_effect = HTTPException(
        status_code=409,
        detail="Inventario duplicado",
    )

    response = client.post(
        BASE_URL,
        headers=auth_headers(users[1]),
        json={
            "producto_id": 10,
            "sucursal_id": 20,
        },
    )

    assert response.status_code == 409


# ============================================================
# ERRORES DE BASE DE DATOS
# ============================================================


@pytest.mark.parametrize(
    "method,path,payload,service_method",
    [
        (
            "GET",
            BASE_URL,
            None,
            "get_all",
        ),
        (
            "GET",
            f"{BASE_URL}/1",
            None,
            "get_by_id",
        ),
        (
            "POST",
            BASE_URL,
            {
                "producto_id": 10,
                "sucursal_id": 20,
            },
            "create",
        ),
        (
            "PATCH",
            f"{BASE_URL}/1",
            {
                "stock_minimo": 8,
            },
            "update_minimum_stock",
        ),
        (
            "POST",
            f"{BASE_URL}/1/entradas",
            {
                "cantidad": 5,
            },
            "register_entry",
        ),
        (
            "POST",
            f"{BASE_URL}/1/salidas",
            {
                "cantidad": 3,
            },
            "register_exit",
        ),
        (
            "POST",
            f"{BASE_URL}/1/ajustes",
            {
                "cantidad_final": 20,
                "motivo": "Conteo",
            },
            "adjust_stock",
        ),
        (
            "POST",
            f"{BASE_URL}/1/traspasos",
            {
                "sucursal_destino_id": 21,
                "cantidad": 4,
            },
            "transfer",
        ),
        (
            "GET",
            f"{BASE_URL}/1/movimientos",
            None,
            "get_movements",
        ),
    ],
)
def test_database_errors_return_503(
    client,
    users,
    service_mock,
    method,
    path,
    payload,
    service_method,
):
    """Los errores SQLAlchemy deben devolver HTTP 503."""

    getattr(
        service_mock,
        service_method,
    ).side_effect = SQLAlchemyError(
        "Database unavailable"
    )

    response = client.request(
        method,
        path,
        headers=auth_headers(users[1]),
        json=payload,
    )

    assert response.status_code == 503


# ============================================================
# DOCUMENTACIÓN OPENAPI
# ============================================================


def test_inventory_endpoints_registered_in_openapi(
    client,
):
    """Comprueba los nueve endpoints en OpenAPI."""

    response = client.get("/openapi.json")

    assert response.status_code == 200

    paths = response.json()["paths"]

    expected = {
        "/inventarios": {
            "get",
            "post",
        },
        "/inventarios/{inventory_id}": {
            "get",
            "patch",
        },
        "/inventarios/{inventory_id}/entradas": {
            "post",
        },
        "/inventarios/{inventory_id}/salidas": {
            "post",
        },
        "/inventarios/{inventory_id}/ajustes": {
            "post",
        },
        "/inventarios/{inventory_id}/traspasos": {
            "post",
        },
        "/inventarios/{inventory_id}/movimientos": {
            "get",
        },
    }

    for path, methods in expected.items():
        assert path in paths
        assert methods.issubset(
            paths[path].keys()
        )
