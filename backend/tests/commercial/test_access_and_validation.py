import pytest
from tests.commercial.test_workflows import sale, payment, confirm, post, invoice_data
from app.modules.customers.model import Customer
from app.modules.inventory.model import Inventory
from app.modules.products.model import Product


@pytest.mark.parametrize("uid", [4, 5])
def test_resource_access_and_lists(security_client, headers, uid):
    c = security_client
    s = sale(c, headers)
    p = payment(c, headers, s["id"])
    assert confirm(c, headers, p["id"]).status_code == 200
    t = c.post(f"/tickets/venta/{s['id']}", headers=headers(2)).json()
    inv = post(c, headers, "/facturas", invoice_data(s["id"]), uid=3).json()
    for path in [
        f"/ventas/{s['id']}",
        f"/pagos/{p['id']}",
        f"/tickets/{t['id']}",
        f"/tickets/{t['id']}/imprimir",
        f"/facturas/{inv['id']}",
    ]:
        assert c.get(path, headers=headers(uid)).status_code == 403, path
    for path, key in [("/ventas", "ventas"), ("/pagos", "pagos")]:
        r = c.get(path, headers=headers(uid))
        assert r.status_code == 200, r.text
        assert r.json()[key] == []
    for path in ["/tickets", "/facturas"]:
        assert c.get(path, headers=headers(uid)).json() == []
    for path in ["/ventas?sucursal_id=2", "/pagos?sucursal_id=2"]:
        assert c.get(path, headers=headers(2)).status_code == 403


@pytest.mark.parametrize(
    "field,value",
    [
        ("monto", "NaN"),
        ("monto", "Infinity"),
        ("monto", "0"),
        ("monto", "-1"),
        ("monto", "60.001"),
        ("cvv", "123"),
        ("numero_tarjeta", "1234567890123456"),
        ("proveedor", "STRIPE"),
        ("estado", "APROBADO"),
        ("confirmado_por", 1),
    ],
)
def test_payment_input_closed(security_client, headers, field, value):
    s = sale(security_client, headers)
    r = post(
        security_client,
        headers,
        "/pagos",
        {"venta_id": s["id"], "metodo": "EFECTIVO", "monto": "60", field: value},
    )
    assert r.status_code == 422, r.text


@pytest.mark.parametrize(
    "change",
    [
        {"rfc": "invalid"},
        {"codigo_postal_fiscal": "24"},
        {"regimen_fiscal": "abc"},
        {"tipo_persona": "MORAL"},
        {"email_fiscal": "invalid"},
        {"uuid": "12345678-1234-4234-8234-123456789abc"},
        {"estado": "EMITIDA"},
    ],
)
def test_invoice_invalid_data(security_client, headers, change):
    s = sale(security_client, headers)
    p = payment(security_client, headers, s["id"])
    confirm(security_client, headers, p["id"])
    r = post(
        security_client,
        headers,
        "/facturas",
        {**invoice_data(s["id"]), **change},
        uid=3,
    )
    assert r.status_code == 422, r.text


def test_invoice_pending_payment_and_external_evidence(security_client, headers):
    c = security_client
    s = sale(c, headers)
    assert (
        post(c, headers, "/facturas", invoice_data(s["id"]), uid=3).status_code == 409
    )
    p = payment(c, headers, s["id"])
    confirm(c, headers, p["id"])
    inv = post(c, headers, "/facturas", invoice_data(s["id"]), uid=3).json()
    assert (
        c.patch(
            f"/facturas/{inv['id']}/estado",
            headers=headers(1),
            json={"estado": "EMITIDA", "motivo": "No evidence"},
        ).status_code
        == 422
    )
    assert (
        c.patch(
            f"/facturas/{inv['id']}/estado",
            headers=headers(1),
            json={"estado": "CANCELADA", "motivo": "Cliente desistió"},
        ).status_code
        == 200
    )
    assert (
        c.patch(
            f"/facturas/{inv['id']}/estado",
            headers=headers(1),
            json={"estado": "CANCELADA", "motivo": "Cliente desistió"},
        ).status_code
        == 409
    )


def test_admin_sale_and_traceability(security_client, security_db, headers):
    r = post(
        security_client,
        headers,
        "/ventas",
        {
            "sucursal_id": 1,
            "empleado_id": 1,
            "productos": [{"producto_id": 1, "cantidad": 2}],
        },
        uid=1,
    )
    assert r.status_code == 201, r.text
    s = r.json()
    assert s["empleado_id"] == 1
    events = security_client.get(
        f"/ventas/{s['id']}/historial", headers=headers(1)
    ).json()
    assert events[0]["usuario_id"] == 1 and events[0]["estado"] == "PENDIENTE"
    assert (
        security_client.get(
            f"/ventas/{s['id']}/historial", headers=headers(3)
        ).status_code
        == 403
    )


def test_profile_and_inactive_customer(security_client, security_db, headers):
    c = security_client
    r = c.post("/mi-perfil", headers=headers(3))
    assert r.status_code == 200, r.text
    assert r.json()["id"] == 10
    assert c.post("/mi-perfil", headers=headers(2)).status_code == 403
    security_db.get(Customer, 10).activo = False
    security_db.commit()
    assert c.post("/mi-perfil", headers=headers(3)).status_code == 403
    assert (
        post(
            c,
            headers,
            "/mis-pedidos",
            {"sucursal_id": 1, "productos": [{"producto_id": 1, "cantidad": 1}]},
            uid=3,
        ).status_code
        == 403
    )


def test_registered_user_can_order_without_admin(security_client, headers):
    c = security_client
    r = c.post(
        "/auth/register",
        json={
            "nombre": "Nuevo",
            "apellido": "Cliente",
            "email": "newcustomer@example.com",
            "password": "SeguraPassword123!",
        },
    )
    assert r.status_code == 201, r.text
    uid = r.json()["id"]
    profile = c.post("/mi-perfil", headers=headers(uid))
    assert profile.status_code == 200, profile.text
    assert (
        post(
            c,
            headers,
            "/mis-pedidos",
            {"sucursal_id": 1, "productos": [{"producto_id": 1, "cantidad": 1}]},
            uid=uid,
        ).status_code
        == 201
    )


def test_new_customer_history(security_client, headers):
    c = security_client
    r = post(
        c,
        headers,
        "/mis-pedidos",
        {"sucursal_id": 1, "productos": [{"producto_id": 1, "cantidad": 1}]},
        uid=3,
    )
    oid = r.json()["id"]
    assert c.post(f"/mis-pedidos/{oid}/cancelar", headers=headers(3)).status_code == 200
    h = c.get(f"/mis-pedidos/{oid}/historial", headers=headers(3))
    assert h.status_code == 200, h.text
    assert [e["estado"] for e in h.json()] == ["PENDIENTE", "CANCELADO"]
    assert c.get(f"/mis-pedidos/{oid}/historial", headers=headers(4)).status_code == 403
    assert c.get(f"/pedidos/{oid}/historial", headers=headers(2)).status_code == 200


def test_zero_total_rejected_atomically(security_client, security_db, headers):
    security_db.get(Product, 1).precio = 0
    security_db.commit()
    r = post(
        security_client,
        headers,
        "/mis-pedidos",
        {"sucursal_id": 1, "productos": [{"producto_id": 1, "cantidad": 1}]},
        uid=3,
    )
    assert r.status_code == 409, r.text
    assert security_db.get(Inventory, 1).cantidad == 20


def test_sales_and_payments_filters(security_client, headers):
    c = security_client
    s = sale(c, headers)
    payment(c, headers, s["id"])
    assert c.get("/ventas?estado=CONFIRMADA", headers=headers(2)).json()["total"] == 0
    assert c.get("/ventas?limit=1&offset=1", headers=headers(2)).json()["ventas"] == []
    assert c.get("/pagos?metodo=SPEI", headers=headers(2)).json()["total"] == 0
    assert (
        c.get("/pagos?desde=2099-01-01T00:00:00Z", headers=headers(2)).json()["total"]
        == 0
    )
    assert c.get("/pagos?estado=PENDIENTE", headers=headers(2)).json()["total"] == 1
    assert c.get("/ventas?limit=101", headers=headers(2)).status_code == 422
    assert (
        c.get("/reportes/productos?menos_vendidos=true", headers=headers(1)).json()[0][
            "cantidad"
        ]
        == 0
    )
    r = c.get("/reportes/movimientos?tipo=VENTA", headers=headers(1))
    assert r.status_code == 200, r.text
    assert len(r.json()) == 1 and r.json()[0]["cantidad"] == 2
    r = c.get("/reportes/inventarios?solo_bajo_stock=true", headers=headers(1))
    assert r.status_code == 200, r.text
    assert r.json() == []


def test_idempotency_header_cors(security_client):
    r = security_client.options(
        "/ventas",
        headers={
            "Origin": "http://localhost:4200",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization,Content-Type,Idempotency-Key",
        },
    )
    assert r.status_code == 200


@pytest.mark.parametrize(
    "uid,role,customer,branch", [(1, 1, None, None), (2, 2, None, 1), (3, 3, 10, None)]
)
def test_session_profile(security_client, headers, uid, role, customer, branch):
    r = security_client.get("/auth/me", headers=headers(uid))
    assert r.status_code == 200, r.text
    assert (
        r.json()["rol_id"] == role
        and r.json()["cliente_id"] == customer
        and r.json()["sucursal_id"] == branch
    )
    assert "password_hash" not in r.text


def test_historical_sale_requires_reconciliation(security_client, security_db, headers):
    from app.modules.sales.model import Sale

    c = security_client
    s = sale(c, headers)
    security_db.get(Sale, s["id"]).vence_at = None
    security_db.commit()
    assert (
        post(
            c,
            headers,
            "/pagos",
            {"venta_id": s["id"], "metodo": "EFECTIVO", "monto": "60"},
        ).status_code
        == 409
    )
    assert (
        c.post(
            f"/ventas/{s['id']}/cancelar",
            headers=headers(1),
            json={"motivo": "Cancelar histórica"},
        ).status_code
        == 409
    )
    assert security_db.get(Inventory, 1).cantidad == 18


def test_branch_ranking_before_pagination(security_client, headers):
    c = security_client
    s = sale(c, headers)
    p = payment(c, headers, s["id"])
    assert confirm(c, headers, p["id"]).status_code == 200
    s2 = post(
        c,
        headers,
        "/ventas",
        {"sucursal_id": 2, "productos": [{"producto_id": 1, "cantidad": 3}]},
        uid=5,
        key="second-branch-sale",
    ).json()
    p2 = post(
        c,
        headers,
        "/pagos",
        {"venta_id": s2["id"], "metodo": "EFECTIVO", "monto": "90"},
        uid=5,
        key="second-branch-payment",
    ).json()
    assert confirm(c, headers, p2["id"], uid=5).status_code == 200
    base = "/reportes/ventas?agrupacion=sucursal&zona_horaria=UTC&limit=1"
    assert (
        c.get(base + "&orden=total_desc", headers=headers(1)).json()[0]["grupo"] == "2"
    )
    assert (
        c.get(base + "&orden=total_asc", headers=headers(1)).json()[0]["grupo"] == "1"
    )
