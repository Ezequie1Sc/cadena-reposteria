
"""Pruebas HTTP de los endpoints de pedidos."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.jwt import create_access_token
from app.core.security import hash_password
from app.db.session import Base, get_db
from app.main import app
from app.modules.users.model import User
from app.shared.models.role_reference import roles_reference


BASE_URL = "/pedidos"
PASSWORD = "PasswordSegura2026!"


# ============================================================
# DATOS DE PRUEBA
# ============================================================


def order_data(estado="PENDIENTE"):
    """Construye una respuesta válida de pedido."""

    now = datetime.now(timezone.utc).isoformat()

    return {
        "id": 50,
        "numero_pedido": "PED-TEST-0001",
        "cliente_id": 1,
        "sucursal_id": 2,
        "estado": estado,
        "subtotal": "60.00",
        "descuento": "0.00",
        "total": "60.00",
        "direccion_entrega": None,
        "notas": None,
        "fecha_pedido": now,
        "created_at": now,
        "updated_at": now,
        "detalles": [
            {
                "id": 100,
                "pedido_id": 50,
                "producto_id": 10,
                "cantidad": 2,
                "precio_unitario": "30.00",
                "descuento": "0.00",
                "subtotal": "60.00",
            }
        ],
    }


def create_payload():
    """Construye una solicitud válida para crear pedidos."""

    return {
        "cliente_id": 1,
        "sucursal_id": 2,
        "productos": [
            {
                "producto_id": 10,
                "cantidad": 2,
            }
        ],
    }


def endpoint_cases():
    """Devuelve las cinco operaciones HTTP del módulo."""

    return [
        (
            "GET",
            BASE_URL,
            None,
        ),
        (
            "GET",
            f"{BASE_URL}/50",
            None,
        ),
        (
            "GET",
            f"{BASE_URL}/numero/PED-TEST-0001",
            None,
        ),
        (
            "POST",
            BASE_URL,
            create_payload(),
        ),
        (
            "PATCH",
            f"{BASE_URL}/50/estado",
            {"estado": "CONFIRMADO"},
        ),
    ]


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def db():
    """Crea SQLite independiente para cada prueba."""

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
    """Crea usuarios con los tres roles disponibles."""

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
            email=f"orders{role_id}@example.com",
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
    """Reemplaza la conexión real por SQLite."""

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(
            get_db,
            None,
        )


@pytest.fixture
def service_mock():
    """Simula las operaciones del servicio de pedidos."""

    with patch(
        "app.modules.orders.routes.order_service"
    ) as mock:

        mock.get_all.return_value = {
            "total": 1,
            "pedidos": [
                order_data(),
            ],
        }

        mock.get_by_id.return_value = order_data()

        mock.get_by_number.return_value = order_data()

        mock.create.return_value = order_data()

        mock.update_status.return_value = order_data(
            estado="CONFIRMADO"
        )

        yield mock


def auth_headers(user):
    """Genera un JWT válido para el usuario."""

    token = create_access_token(user.id)

    return {
        "Authorization": f"Bearer {token}",
    }


# ============================================================
# AUTENTICACIÓN Y AUTORIZACIÓN
# ============================================================


@pytest.mark.parametrize(
    "method,path,payload",
    endpoint_cases(),
)
def test_routes_require_authentication(
    client,
    method,
    path,
    payload,
):
    """Todos los endpoints requieren autenticación."""

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
def test_customer_cannot_access_orders(
    client,
    users,
    method,
    path,
    payload,
):
    """Los clientes no pueden administrar pedidos."""

    response = client.request(
        method,
        path,
        headers=auth_headers(users[3]),
        json=payload,
    )

    assert response.status_code == 403


@pytest.mark.parametrize(
    "role_id",
    [1, 2],
)
def test_staff_can_list_orders(
    client,
    users,
    service_mock,
    role_id,
):
    """Administradores y empleados pueden consultar pedidos."""

    response = client.get(
        BASE_URL,
        headers=auth_headers(users[role_id]),
    )

    assert response.status_code == 200

    result = response.json()

    assert result["total"] == 1
    assert len(result["pedidos"]) == 1

    service_mock.get_all.assert_called_once()


def test_inactive_user_returns_401(
    client,
    db,
    users,
):
    """Un usuario inactivo pierde acceso al módulo."""

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
    """Un rol desactivado no permite acceder a pedidos."""

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
# CONSULTAS DE PEDIDOS
# ============================================================


def test_list_orders_with_filters(
    client,
    users,
    service_mock,
):
    """Los filtros se transmiten al servicio."""

    response = client.get(
        BASE_URL,
        params={
            "cliente_id": 1,
            "sucursal_id": 2,
            "estado": "PENDIENTE",
            "limit": 10,
            "offset": 0,
        },
        headers=auth_headers(users[2]),
    )

    assert response.status_code == 200

    service_mock.get_all.assert_called_once()

    kwargs = service_mock.get_all.call_args.kwargs

    assert kwargs["cliente_id"] == 1
    assert kwargs["sucursal_id"] == 2
    assert kwargs["estado"] == "PENDIENTE"
    assert kwargs["limit"] == 10
    assert kwargs["offset"] == 0


def test_get_order(
    client,
    users,
    service_mock,
):
    """Consulta un pedido por su identificador."""

    response = client.get(
        f"{BASE_URL}/50",
        headers=auth_headers(users[2]),
    )

    assert response.status_code == 200

    result = response.json()

    assert result["id"] == 50
    assert len(result["detalles"]) == 1

    service_mock.get_by_id.assert_called_once()

    args = service_mock.get_by_id.call_args.args

    assert len(args) == 2
    assert args[1] == 50


def test_get_order_by_number(
    client,
    users,
    service_mock,
):
    """Consulta un pedido mediante su número."""

    response = client.get(
        f"{BASE_URL}/numero/PED-TEST-0001",
        headers=auth_headers(users[2]),
    )

    assert response.status_code == 200

    assert response.json()["numero_pedido"] == (
        "PED-TEST-0001"
    )

    service_mock.get_by_number.assert_called_once()


def test_missing_order_returns_404(
    client,
    users,
    service_mock,
):
    """Un pedido inexistente produce HTTP 404."""

    service_mock.get_by_id.side_effect = HTTPException(
        status_code=404,
        detail="Pedido no encontrado",
    )

    response = client.get(
        f"{BASE_URL}/999",
        headers=auth_headers(users[2]),
    )

    assert response.status_code == 404


# ============================================================
# CREACIÓN DE PEDIDOS
# ============================================================


@pytest.mark.parametrize(
    "role_id",
    [1, 2],
)
def test_create_order(
    client,
    users,
    service_mock,
    role_id,
):
    """Crea un pedido y registra al usuario responsable."""

    response = client.post(
        BASE_URL,
        json=create_payload(),
        headers=auth_headers(users[role_id]),
    )

    assert response.status_code == 201
    assert response.json()["id"] == 50

    service_mock.create.assert_called_once()

    args = service_mock.create.call_args.args
    kwargs = service_mock.create.call_args.kwargs

    # El servicio recibe db y data por posición.
    assert len(args) == 2

    db_session = args[0]
    order_payload = args[1]

    assert db_session is not None

    assert order_payload.cliente_id == 1
    assert order_payload.sucursal_id == 2

    assert len(order_payload.productos) == 1

    assert (
        order_payload.productos[0].producto_id
        == 10
    )

    assert (
        order_payload.productos[0].cantidad
        == 2
    )

    # El identificador del usuario se pasa por nombre.
    assert kwargs["usuario_id"] == users[role_id].id


def test_create_rejects_zero_quantity(
    client,
    users,
    service_mock,
):
    """No permite productos con cantidad igual a cero."""

    payload = create_payload()

    payload["productos"][0]["cantidad"] = 0

    response = client.post(
        BASE_URL,
        json=payload,
        headers=auth_headers(users[2]),
    )

    assert response.status_code == 422

    service_mock.create.assert_not_called()


def test_create_rejects_duplicate_products(
    client,
    users,
    service_mock,
):
    """No permite repetir productos dentro del pedido."""

    payload = create_payload()

    payload["productos"].append(
        {
            "producto_id": 10,
            "cantidad": 1,
        }
    )

    response = client.post(
        BASE_URL,
        json=payload,
        headers=auth_headers(users[2]),
    )

    assert response.status_code == 422

    service_mock.create.assert_not_called()


def test_insufficient_stock_returns_409(
    client,
    users,
    service_mock,
):
    """El stock insuficiente produce HTTP 409."""

    service_mock.create.side_effect = HTTPException(
        status_code=409,
        detail="Existencias insuficientes",
    )

    response = client.post(
        BASE_URL,
        json=create_payload(),
        headers=auth_headers(users[2]),
    )

    assert response.status_code == 409


# ============================================================
# ACTUALIZACIÓN DE ESTADOS
# ============================================================


def test_update_status(
    client,
    users,
    service_mock,
):
    """Actualiza correctamente el estado de un pedido."""

    response = client.patch(
        f"{BASE_URL}/50/estado",
        json={
            "estado": "CONFIRMADO",
        },
        headers=auth_headers(users[2]),
    )

    assert response.status_code == 200

    assert response.json()["estado"] == "CONFIRMADO"

    service_mock.update_status.assert_called_once()

    kwargs = service_mock.update_status.call_args.kwargs

    assert kwargs["usuario_id"] == users[2].id


def test_invalid_transition_returns_409(
    client,
    users,
    service_mock,
):
    """Una transición no permitida produce HTTP 409."""

    service_mock.update_status.side_effect = (
        HTTPException(
            status_code=409,
            detail="Transición no permitida",
        )
    )

    response = client.patch(
        f"{BASE_URL}/50/estado",
        json={
            "estado": "ENTREGADO",
        },
        headers=auth_headers(users[2]),
    )

    assert response.status_code == 409


def test_invalid_status_returns_422(
    client,
    users,
    service_mock,
):
    """Un estado desconocido produce HTTP 422."""

    response = client.patch(
        f"{BASE_URL}/50/estado",
        json={
            "estado": "DESCONOCIDO",
        },
        headers=auth_headers(users[2]),
    )

    assert response.status_code == 422

    service_mock.update_status.assert_not_called()


# ============================================================
# ERRORES DE BASE DE DATOS
# ============================================================


def test_database_failure_returns_503(
    client,
    users,
    service_mock,
):
    """Un error SQL se transforma en HTTP 503."""

    service_mock.get_all.side_effect = OperationalError(
        "SELECT",
        {},
        Exception("database unavailable"),
    )

    response = client.get(
        BASE_URL,
        headers=auth_headers(users[2]),
    )

    assert response.status_code == 503

    assert response.json()["detail"] == (
        "No fue posible consultar los pedidos"
    )
