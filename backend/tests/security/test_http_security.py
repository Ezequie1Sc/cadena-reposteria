"""Security regressions against the complete app, without auth overrides."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch
import re
import jwt
import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from app.main import app
from app.core.config import settings
from app.modules.users.model import User
from app.modules.inventory.model import Inventory, InventoryMovement
from app.modules.orders.model import Order
from app.modules.customers.model import Customer
from app.modules.employees.model import Employee
from app.modules.branches.model import Branch

PUBLIC = {
    ("GET", "/"),
    ("GET", "/health"),
    ("POST", "/auth/login"),
    ("POST", "/auth/register"),
}
PRIVATE = [
    (m.upper(), p)
    for p, ops in app.openapi()["paths"].items()
    for m in ops
    if m in {"get", "post", "patch", "delete", "put"} and (m.upper(), p) not in PUBLIC
]


def url(path):
    return re.sub(r"\{[^}]+\}", "1", path)


def expired_token():
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": "1",
            "type": "access",
            "iat": now - timedelta(hours=2),
            "nbf": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


@pytest.mark.parametrize("method,path", PRIVATE)
@pytest.mark.parametrize("credential", ["missing", "invalid", "expired", "inactive"])
def test_every_private_operation_rejects_invalid_identity(
    security_client, security_db, headers, method, path, credential
):
    auth = {}
    if credential == "invalid":
        auth = {"Authorization": "Bearer not-a-token"}
    if credential == "expired":
        auth = {"Authorization": f"Bearer {expired_token()}"}
    if credential == "inactive":
        security_db.get(User, 1).activo = False
        security_db.commit()
        auth = headers(1)
    r = security_client.request(
        method,
        url(path),
        headers=auth,
        json={} if method in {"POST", "PATCH"} else None,
    )
    assert r.status_code == 401, (method, path, r.text)
    assert r.headers["www-authenticate"] == "Bearer"


ADMIN_ONLY = [
    (m, p)
    for m, p in PRIVATE
    if p.startswith(("/usuarios", "/empleados", "/roles", "/health/database"))
    or (p.startswith(("/productos", "/categorias", "/sucursales")) and m != "GET")
    or p == "/clientes"
    or (p.startswith("/clientes/") and (m == "DELETE" or p.endswith("/reactivar")))
]


@pytest.mark.parametrize("method,path", ADMIN_ONLY)
@pytest.mark.parametrize("uid", [2, 3])
def test_vertical_escalation_denied(security_client, headers, method, path, uid):
    r = security_client.request(
        method,
        url(path),
        headers=headers(uid),
        json={} if method in {"POST", "PATCH"} else None,
    )
    assert r.status_code == 403, (method, path, r.text)


@pytest.mark.parametrize(
    "method,path,payload",
    [
        ("GET", "/inventarios/2", None),
        ("GET", "/inventarios/2/movimientos", None),
        ("POST", "/inventarios/2/entradas", {"cantidad": 3}),
        ("POST", "/inventarios/2/salidas", {"cantidad": 3}),
        ("GET", "/inventarios?sucursal_id=2", None),
        ("GET", "/pedidos?sucursal_id=2", None),
        ("GET", "/pedidos/22", None),
        ("GET", "/pedidos/numero/PED-2", None),
        ("PATCH", "/pedidos/22/estado", {"estado": "CANCELADO"}),
        (
            "POST",
            "/pedidos",
            {
                "cliente_id": 11,
                "sucursal_id": 2,
                "productos": [{"producto_id": 1, "cantidad": 2}],
            },
        ),
    ],
)
def test_employee_cannot_cross_branch(
    security_client, security_db, headers, method, path, payload
):
    r = security_client.request(method, path, headers=headers(2), json=payload)
    assert r.status_code == 403, r.text
    assert security_db.get(Inventory, 2).cantidad == 20
    assert security_db.get(Order, 22).estado == "PENDIENTE"
    assert len(security_db.scalars(select(InventoryMovement)).all()) == 0


@pytest.mark.parametrize(
    "path,key", [("/inventarios", "inventarios"), ("/pedidos", "pedidos")]
)
def test_employee_lists_scoped(security_client, headers, path, key):
    r = security_client.get(path, headers=headers(2))
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 1
    assert {x["sucursal_id"] for x in r.json()[key]} == {1}


@pytest.mark.parametrize(
    "state", ["employee_inactive", "branch_inactive", "unassigned"]
)
def test_assignment_must_remain_active(security_client, security_db, headers, state):
    employee = security_db.scalar(select(Employee).where(Employee.usuario_id == 2))
    if state == "employee_inactive":
        employee.activo = False
    if state == "branch_inactive":
        security_db.get(Branch, 1).activo = False
    if state == "unassigned":
        security_db.delete(employee)
    security_db.commit()
    for path in ["/inventarios", "/pedidos"]:
        assert security_client.get(path, headers=headers(2)).status_code == 403


def test_admin_can_manage_catalog_and_employees(security_client, headers):
    r = security_client.post(
        "/categorias", headers=headers(1), json={"nombre": "Galletas"}
    )
    assert r.status_code == 201, r.text
    r = security_client.post(
        "/productos",
        headers=headers(1),
        json={
            "categoria_id": r.json()["id"],
            "nombre": "Galleta",
            "sku": "GAL-01",
            "precio": "20.00",
        },
    )
    assert r.status_code == 201, r.text
    r = security_client.patch(
        "/empleados/1", headers=headers(1), json={"puesto": "Supervisor"}
    )
    assert r.status_code == 200, r.text
    assert security_client.get("/roles", headers=headers(1)).status_code == 200
    assert (
        security_client.get("/health/database", headers=headers(1)).status_code == 200
    )


@pytest.mark.parametrize(
    "method,path,payload,expected",
    [
        ("GET", "/clientes/10", None, 200),
        ("PATCH", "/clientes/10", {"nombre": "Mi nombre"}, 200),
        ("GET", "/clientes/11", None, 403),
        ("PATCH", "/clientes/11", {"nombre": "Intrusión"}, 403),
        ("PATCH", "/clientes/10", {"usuario_id": 4}, 403),
        ("PATCH", "/clientes/10", {"usuario_id": None}, 403),
        ("PATCH", "/clientes/10", {"activo": False}, 422),
        ("PATCH", "/clientes/10", {"rol_id": 1}, 422),
    ],
)
def test_customer_ownership(
    security_client, security_db, headers, method, path, payload, expected
):
    r = security_client.request(method, path, headers=headers(3), json=payload)
    assert r.status_code == expected, r.text
    assert security_db.get(Customer, 10).usuario_id == 3
    assert security_db.get(Customer, 11).nombre == "Cliente"


def test_deactivated_customer_cannot_edit_self(security_client, security_db, headers):
    security_db.get(Customer, 10).activo = False
    security_db.commit()
    assert (
        security_client.patch(
            "/clientes/10", headers=headers(3), json={"nombre": "Cambio"}
        ).status_code
        == 403
    )


@pytest.mark.parametrize("uid", [2, 3])
def test_inactive_catalog_is_private(security_client, security_db, headers, uid):
    from app.modules.products.model import Product

    security_db.get(Product, 1).activo = False
    security_db.commit()
    assert security_client.get("/productos/1", headers=headers(uid)).status_code == 404
    assert (
        security_client.get(
            "/productos?solo_activos=false", headers=headers(uid)
        ).status_code
        == 403
    )
    assert security_client.get("/productos", headers=headers(uid)).json()["total"] == 0


def test_employee_order_lifecycle_preserves_stock(
    security_client, security_db, headers
):
    r = security_client.post(
        "/pedidos",
        headers=headers(2),
        json={
            "cliente_id": 10,
            "sucursal_id": 1,
            "productos": [{"producto_id": 1, "cantidad": 3}],
        },
    )
    assert r.status_code == 201, r.text
    oid = r.json()["id"]
    assert Decimal(r.json()["total"]) == Decimal("90.00")
    assert security_db.get(Inventory, 1).cantidad == 17
    r = security_client.patch(
        f"/pedidos/{oid}/estado", headers=headers(2), json={"estado": "CANCELADO"}
    )
    assert r.status_code == 200, r.text
    assert security_db.get(Inventory, 1).cantidad == 20
    assert (
        security_client.patch(
            f"/pedidos/{oid}/estado", headers=headers(2), json={"estado": "CANCELADO"}
        ).status_code
        == 409
    )
    assert security_db.get(Inventory, 1).cantidad == 20
    movements = security_db.scalars(
        select(InventoryMovement).where(InventoryMovement.referencia_id == oid)
    ).all()
    assert len(movements) == 2 and {m.usuario_id for m in movements} == {2}


def test_employee_entries_exits_and_oversell(security_client, security_db, headers):
    assert (
        security_client.post(
            "/inventarios/1/entradas", headers=headers(2), json={"cantidad": 5}
        ).status_code
        == 200
    )
    assert (
        security_client.post(
            "/inventarios/1/salidas", headers=headers(2), json={"cantidad": 3}
        ).status_code
        == 200
    )
    assert (
        security_client.post(
            "/inventarios/1/salidas", headers=headers(2), json={"cantidad": 100}
        ).status_code
        == 409
    )
    assert security_db.get(Inventory, 1).cantidad == 22


@pytest.mark.parametrize(
    "path,payload",
    [
        ("/auth/login", {"email": "x", "password": {"secret": "MustNotEcho123"}}),
        (
            "/auth/register",
            {
                "nombre": "Test",
                "apellido": "Test",
                "email": "a@example.com",
                "password": "MustNotEcho123",
                "rol_id": {"secret": "MustNotEcho123"},
            },
        ),
    ],
)
def test_validation_never_echoes_input(security_client, path, payload):
    r = security_client.post(path, json=payload)
    assert r.status_code == 422
    assert "MustNotEcho123" not in r.text
    assert all("input" not in e and "ctx" not in e for e in r.json()["detail"])


def test_rate_limit_ignores_forwarded_for(security_client):
    for i in range(6):
        r = security_client.post(
            "/auth/login",
            headers={"X-Forwarded-For": f"192.0.2.{i}"},
            json={"email": "missing@example.com", "password": "wrong"},
        )
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0


def test_rate_limit_failure_closed(security_client):
    with patch(
        "app.core.rate_limit.rate_limit_repository.record_attempt",
        side_effect=OperationalError("SQL SECRET", {}, Exception("private-password")),
    ):
        r = security_client.post(
            "/auth/login",
            json={"email": "user1@example.com", "password": "AuditPassword2026!"},
        )
    assert r.status_code == 503
    assert (
        "SECRET" not in r.text
        and "private-password" not in r.text
        and "access_token" not in r.text
    )


def test_registration_password_spaces(security_client, security_db):
    password = "  AuditPassword2026!  "
    r = security_client.post(
        "/auth/register",
        json={
            "nombre": "Nuevo",
            "apellido": "Cliente",
            "email": "new@example.com",
            "password": password,
        },
    )
    assert r.status_code == 201, r.text
    assert (
        security_db.scalar(select(User).where(User.email == "new@example.com")).rol_id
        == 3
    )
    assert (
        security_client.post(
            "/auth/login", json={"email": "new@example.com", "password": password}
        ).status_code
        == 200
    )
    assert (
        security_client.post(
            "/auth/login",
            json={"email": "new@example.com", "password": password.strip()},
        ).status_code
        == 401
    )


def test_explicit_cors(security_client):
    h = {"Origin": "https://untrusted.example", "Access-Control-Request-Method": "GET"}
    assert (
        "access-control-allow-origin"
        not in security_client.options("/productos", headers=h).headers
    )
    h["Origin"] = "http://localhost:4200"
    assert (
        security_client.options("/productos", headers=h).headers[
            "access-control-allow-origin"
        ]
        == "http://localhost:4200"
    )


def test_openapi_all_private_operations_document_security():
    assert len(PRIVATE) == 88  # 52 original operations + 36 new protected operations
    for m, p in PRIVATE:
        assert app.openapi()["paths"][p][m.lower()].get("security"), (m, p)


@pytest.mark.parametrize(
    "path,payload",
    [
        ("/inventarios/1/entradas", {"cantidad": 1, "usuario_id": 1}),
        ("/inventarios/1/salidas", {"cantidad": 1, "referencia_tipo": "VENTA"}),
        (
            "/pedidos",
            {
                "cliente_id": 10,
                "sucursal_id": 1,
                "total": 0,
                "productos": [{"producto_id": 1, "cantidad": 1}],
            },
        ),
        (
            "/pedidos",
            {
                "cliente_id": 10,
                "sucursal_id": 1,
                "productos": [{"producto_id": 1, "cantidad": 1, "precio_unitario": 0}],
            },
        ),
    ],
)
def test_mass_assignment_rejected(security_client, security_db, headers, path, payload):
    assert (
        security_client.post(path, headers=headers(2), json=payload).status_code == 422
    )
    assert security_db.get(Inventory, 1).cantidad == 20


@pytest.mark.parametrize(
    "path",
    [
        "/productos",
        "/categorias",
        "/sucursales",
        "/clientes/10",
        "/inventarios",
        "/pedidos",
        "/usuarios",
    ],
)
def test_unknown_role_denied(security_client, headers, path):
    assert security_client.get(path, headers=headers(6)).status_code == 403


@pytest.mark.parametrize("scheme", ["Basic abc", "Bearer", "Digest abc"])
def test_wrong_authorization_scheme(security_client, scheme):
    r = security_client.get("/productos", headers={"Authorization": scheme})
    assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"


def test_unexpected_exception_has_no_traceback(security_client, headers):
    with patch(
        "app.modules.products.routes.product_service.get_products",
        side_effect=RuntimeError("private credential value"),
    ):
        r = security_client.get("/productos", headers=headers(1))
    assert r.status_code == 500
    assert r.json() == {"detail": "Error interno del servidor"}
