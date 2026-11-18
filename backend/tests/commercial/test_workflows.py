from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch
import pytest
from sqlalchemy import select, func
from app.modules.sales.model import Sale
from app.modules.payments.model import Payment, PaymentMethod
from app.modules.inventory.model import Inventory, InventoryMovement
from app.modules.products.model import Product
from app.modules.branches.model import Branch
from app.shared.commerce_models import CommercialEvent, IdempotencyRecord


def post(client, headers, path, data, uid=2, key="test-operation-01"):
    return client.post(
        path, json=data, headers={**headers(uid), "Idempotency-Key": key}
    )


def sale(client, headers, qty=2, key="sale-test-01", **changes):
    data = {
        "sucursal_id": 1,
        "cliente_id": 10,
        "productos": [{"producto_id": 1, "cantidad": qty}],
        **changes,
    }
    r = post(client, headers, "/ventas", data, key=key)
    assert r.status_code == 201, r.text
    return r.json()


def payment(client, headers, sid, method="EFECTIVO", key="payment-test-01", uid=2):
    data = {"venta_id": sid, "metodo": method, "monto": "60.00"}
    if method != "EFECTIVO":
        data["referencia"] = "Referencia manual de prueba"
    r = post(client, headers, "/pagos", data, uid=uid, key=key)
    assert r.status_code == 201, r.text
    return r.json()


def confirm(client, headers, pid, state="APROBADO", uid=2):
    return client.patch(
        f"/pagos/{pid}/estado",
        headers=headers(uid),
        json={"estado": state, "motivo": "Verificado manualmente"},
    )


def invoice_data(sid):
    return dict(
        venta_id=sid,
        cliente_id=10,
        rfc="XAXX010101000",
        razon_social="Cliente de prueba",
        uso_cfdi="G03",
        codigo_postal_fiscal="24000",
        regimen_fiscal="616",
        tipo_persona="FISICA",
        direccion_fiscal="Calle de prueba 1",
        email_fiscal="customer@example.com",
    )


def test_sale_payment_ticket_invoice_complete(security_client, security_db, headers):
    c = security_client
    s = sale(c, headers)
    assert Decimal(s["total"]) == 60 and security_db.get(Inventory, 1).cantidad == 18
    ticket = c.post(f"/tickets/venta/{s['id']}", headers=headers(2))
    assert ticket.status_code == 200, ticket.text
    assert not ticket.json()["pagado"]
    assert (
        c.post(f"/tickets/venta/{s['id']}", headers=headers(2)).json()["id"]
        == ticket.json()["id"]
    )
    p = payment(c, headers, s["id"])
    assert p["estado"] == "PENDIENTE" and p["confirmado_por"] is None
    r = confirm(c, headers, p["id"])
    assert r.status_code == 200, r.text
    assert r.json()["confirmado_por"] == 2
    assert confirm(c, headers, p["id"]).status_code == 409
    security_db.get(Product, 1).precio = 999
    security_db.commit()
    t = c.get(f"/tickets/{ticket.json()['id']}", headers=headers(3)).json()
    assert t["pagado"] and Decimal(t["venta"]["total"]) == 60
    assert Decimal(t["venta"]["detalles"][0]["precio_unitario"]) == 30
    html = c.get(f"/tickets/{t['id']}/imprimir", headers=headers(3))
    assert (
        html.status_code == 200 and "60.00" in html.text and "No es CFDI" in html.text
    )
    inv = post(c, headers, "/facturas", invoice_data(s["id"]), uid=3)
    assert inv.status_code == 201, inv.text
    assert inv.json()["estado"] == "PENDIENTE" and inv.json()["uuid"] is None
    assert (
        post(c, headers, "/facturas", invoice_data(s["id"]), uid=3).json()["id"]
        == inv.json()["id"]
    )
    assert c.get(f"/facturas/{inv.json()['id']}", headers=headers(4)).status_code == 403
    assert (
        c.patch(
            f"/facturas/{inv.json()['id']}/estado",
            headers=headers(3),
            json={"estado": "CANCELADA", "motivo": "Cancelación solicitada"},
        ).status_code
        == 403
    )
    r = c.patch(
        f"/facturas/{inv.json()['id']}/estado",
        headers=headers(1),
        json={
            "estado": "EMITIDA",
            "motivo": "Documento externo verificado",
            "uuid": "12345678-1234-4234-8234-123456789abc",
            "proveedor": "PAC externo",
            "referencia_proveedor": "Documento externo 123",
            "fecha_emision": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert r.status_code == 200, r.text
    assert (
        c.post(
            f"/ventas/{s['id']}/cancelar",
            headers=headers(1),
            json={"motivo": "Devolución solicitada", "reembolso_referencia": "DEV001"},
        ).status_code
        == 409
    )


def test_idempotency_and_stock(security_client, security_db, headers):
    s = sale(security_client, headers)
    assert sale(security_client, headers)["id"] == s["id"]
    r = post(
        security_client,
        headers,
        "/ventas",
        {
            "sucursal_id": 1,
            "cliente_id": 10,
            "productos": [{"producto_id": 1, "cantidad": 3}],
        },
        key="sale-test-01",
    )
    assert r.status_code == 409
    assert security_db.get(Inventory, 1).cantidad == 18
    assert security_db.scalar(select(func.count()).select_from(Sale)) == 1


@pytest.mark.parametrize(
    "change,expected",
    [
        ({"productos": [{"producto_id": 999, "cantidad": 1}]}, 404),
        ({"productos": [{"producto_id": 1, "cantidad": 0}]}, 422),
        ({"productos": [{"producto_id": 1, "cantidad": -1}]}, 422),
        ({"productos": [{"producto_id": 1, "cantidad": 21}]}, 409),
        ({"productos": [{"producto_id": 1, "cantidad": 1, "precio_unitario": 1}]}, 422),
        (
            {
                "productos": [
                    {"producto_id": 1, "cantidad": 1},
                    {"producto_id": 1, "cantidad": 1},
                ]
            },
            422,
        ),
        ({"total": "1.00"}, 422),
        ({"sucursal_id": 2}, 403),
        ({"empleado_id": 2}, 403),
    ],
)
def test_invalid_sales_atomic(security_client, security_db, headers, change, expected):
    r = post(
        security_client,
        headers,
        "/ventas",
        {"sucursal_id": 1, "productos": [{"producto_id": 1, "cantidad": 2}], **change},
    )
    assert r.status_code == expected, r.text
    assert security_db.get(Inventory, 1).cantidad == 20
    assert security_db.scalar(select(func.count()).select_from(Sale)) == 0


@pytest.mark.parametrize("target", ["product", "method", "branch"])
def test_inactive_records(security_client, security_db, headers, target):
    if target == "method":
        s = sale(security_client, headers)
        security_db.get(PaymentMethod, 1).activo = False
        security_db.commit()
        r = post(
            security_client,
            headers,
            "/pagos",
            {"venta_id": s["id"], "metodo": "EFECTIVO", "monto": "60"},
        )
        assert r.status_code == 409
    else:
        security_db.get(Product if target == "product" else Branch, 1).activo = False
        security_db.commit()
        r = post(
            security_client,
            headers,
            "/ventas",
            {"sucursal_id": 1, "productos": [{"producto_id": 1, "cantidad": 1}]},
        )
        assert r.status_code in {403, 409}
        assert security_db.get(Inventory, 1).cantidad == 20


@pytest.mark.parametrize("method", ["EFECTIVO", "SPEI", "DEPOSITO", "TARJETA"])
def test_manual_methods(security_client, headers, method):
    s = sale(security_client, headers)
    p = payment(security_client, headers, s["id"], method)
    assert p["estado"] == "PENDIENTE"
    assert confirm(security_client, headers, p["id"]).status_code == 200


@pytest.mark.parametrize("state", ["RECHAZADO", "CANCELADO"])
def test_payment_rejection_retry_reserves_once(
    security_client, security_db, headers, state
):
    s = sale(security_client, headers)
    p = payment(security_client, headers, s["id"])
    assert confirm(security_client, headers, p["id"], state).status_code == 200
    assert security_db.get(Inventory, 1).cantidad == 18
    retry = payment(security_client, headers, s["id"], key="second-payment")
    assert confirm(security_client, headers, retry["id"]).status_code == 200
    assert security_db.get(Inventory, 1).cantidad == 18


def test_payment_conflicts(security_client, headers):
    s = sale(security_client, headers)
    for amount in ["1.00", "61.00"]:
        r = post(
            security_client,
            headers,
            "/pagos",
            {"venta_id": s["id"], "metodo": "EFECTIVO", "monto": amount},
        )
        assert r.status_code == 409, r.text
    p = payment(security_client, headers, s["id"])
    assert payment(security_client, headers, s["id"])["id"] == p["id"]
    assert (
        post(
            security_client,
            headers,
            "/pagos",
            {"venta_id": s["id"], "metodo": "EFECTIVO", "monto": "60.00"},
            key="other-key-01",
        ).status_code
        == 409
    )
    assert confirm(security_client, headers, p["id"], uid=3).status_code == 403
    assert confirm(security_client, headers, p["id"], uid=5).status_code == 403


@pytest.mark.parametrize("paid", [False, True])
def test_cancellation_and_refund(security_client, security_db, headers, paid):
    c = security_client
    s = sale(c, headers)
    p = payment(c, headers, s["id"])
    if paid:
        assert confirm(c, headers, p["id"]).status_code == 200
        assert (
            c.post(
                f"/ventas/{s['id']}/cancelar",
                headers=headers(2),
                json={"motivo": "Cancelar venta"},
            ).status_code
            == 403
        )
        assert (
            c.post(
                f"/ventas/{s['id']}/cancelar",
                headers=headers(1),
                json={"motivo": "Cancelar venta"},
            ).status_code
            == 409
        )
    body = {"motivo": "Cancelación solicitada", "reembolso_referencia": "DEV-001"}
    r = c.post(f"/ventas/{s['id']}/cancelar", headers=headers(1), json=body)
    assert r.status_code == 200, r.text
    assert security_db.get(Inventory, 1).cantidad == 20
    assert security_db.get(Payment, p["id"]).estado == (
        "REEMBOLSADO" if paid else "CANCELADO"
    )
    assert (
        c.post(f"/ventas/{s['id']}/cancelar", headers=headers(1), json=body).status_code
        == 409
    )
    assert security_db.get(Inventory, 1).cantidad == 20
    assert security_db.scalar(select(func.count()).select_from(InventoryMovement)) == 2


def test_expiration(security_client, security_db, headers):
    s = sale(security_client, headers)
    p = payment(security_client, headers, s["id"])
    security_db.get(Sale, s["id"]).vence_at = datetime.now(timezone.utc) - timedelta(
        minutes=1
    )
    security_db.commit()
    assert confirm(security_client, headers, p["id"]).status_code == 409
    assert (
        security_client.post("/ventas/expirar", headers=headers(2)).status_code == 403
    )
    r = security_client.post("/ventas/expirar", headers=headers(1))
    assert r.status_code == 200, r.text
    assert r.json()["ventas_canceladas"] == [s["id"]]
    assert security_db.get(Inventory, 1).cantidad == 20
    assert (
        security_client.post("/ventas/expirar", headers=headers(1)).json()[
            "ventas_canceladas"
        ]
        == []
    )


def test_client_order_to_delivery(security_client, security_db, headers):
    c = security_client
    data = {
        "sucursal_id": 1,
        "productos": [{"producto_id": 1, "cantidad": 2}],
        "direccion_entrega": "Recoger en sucursal",
    }
    r = post(c, headers, "/mis-pedidos", data, uid=3)
    assert r.status_code == 201, r.text
    oid = r.json()["id"]
    assert post(c, headers, "/mis-pedidos", data, uid=3).json()["id"] == oid
    assert security_db.get(Inventory, 1).cantidad == 18
    assert (
        post(c, headers, "/mis-pedidos", {**data, "cliente_id": 11}, uid=3).status_code
        == 422
    )
    assert c.get(f"/mis-pedidos/{oid}", headers=headers(4)).status_code == 403
    assert all(
        x["cliente_id"] == 10
        for x in c.get("/mis-pedidos", headers=headers(3)).json()["pedidos"]
    )
    assert (
        c.patch(
            f"/pedidos/{oid}/estado", headers=headers(2), json={"estado": "CONFIRMADO"}
        ).status_code
        == 409
    )
    p = post(
        c,
        headers,
        "/pagos",
        {
            "pedido_id": oid,
            "metodo": "SPEI",
            "monto": "60.00",
            "referencia": "SPEI referencia",
        },
        uid=3,
    )
    assert p.status_code == 201, p.text
    assert confirm(c, headers, p.json()["id"], uid=3).status_code == 403
    assert confirm(c, headers, p.json()["id"]).status_code == 200
    assert c.post(f"/mis-pedidos/{oid}/cancelar", headers=headers(3)).status_code == 403
    for state in ["PREPARANDO", "LISTO", "ENTREGADO"]:
        r = c.patch(
            f"/pedidos/{oid}/estado", headers=headers(2), json={"estado": state}
        )
        assert r.status_code == 200, r.text
    assert security_db.get(Inventory, 1).cantidad == 18
    assert (
        c.patch(
            f"/pedidos/{oid}/estado", headers=headers(2), json={"estado": "CANCELADO"}
        ).status_code
        == 409
    )


def test_client_cancel_and_stock(security_client, security_db, headers):
    c = security_client
    r = post(
        c,
        headers,
        "/mis-pedidos",
        {"sucursal_id": 1, "productos": [{"producto_id": 1, "cantidad": 2}]},
        uid=3,
    )
    assert r.status_code == 201, r.text
    oid = r.json()["id"]
    assert c.post(f"/mis-pedidos/{oid}/cancelar", headers=headers(4)).status_code == 403
    assert c.post(f"/mis-pedidos/{oid}/cancelar", headers=headers(3)).status_code == 200
    assert c.post(f"/mis-pedidos/{oid}/cancelar", headers=headers(3)).status_code == 409
    assert security_db.get(Inventory, 1).cantidad == 20


def test_reports_actual_totals_filters_and_roles(security_client, headers):
    c = security_client
    s = sale(c, headers)
    p = payment(c, headers, s["id"])
    pending = c.get("/reportes/pagos?solo_confirmados=true", headers=headers(1))
    assert pending.status_code == 200, pending.text
    assert pending.json() == []
    assert confirm(c, headers, p["id"]).status_code == 200
    for grouping in ["dia", "semana", "mes", "anio", "sucursal", "empleado"]:
        r = c.get(
            f"/reportes/ventas?agrupacion={grouping}&zona_horaria=UTC",
            headers=headers(1),
        )
        assert r.status_code == 200, r.text
        assert sum(Decimal(x["total"]) for x in r.json()) == 60
    assert (
        c.get(
            "/reportes/ventas?sucursal_id=2&zona_horaria=UTC", headers=headers(1)
        ).json()
        == []
    )
    assert (
        c.get(
            "/reportes/ventas?desde=2099-01-01T00:00:00Z&zona_horaria=UTC",
            headers=headers(1),
        ).json()
        == []
    )
    assert (
        c.get("/reportes/ventas?desde=2026-01-01", headers=headers(1)).status_code
        == 422
    )
    assert (
        c.get(
            "/reportes/ventas?desde=2027-01-01T00:00:00Z&hasta=2026-01-01T00:00:00Z",
            headers=headers(1),
        ).status_code
        == 422
    )
    d = c.get("/reportes/dashboard?zona_horaria=UTC", headers=headers(1))
    assert d.status_code == 200, d.text
    assert Decimal(d.json()["ingresos_mes"]) == 60 and d.json()["ventas_dia"] == 1
    for endpoint in [
        "ventas",
        "productos",
        "pagos",
        "inventarios",
        "movimientos",
        "dashboard",
    ]:
        for uid in [2, 3]:
            assert (
                c.get(f"/reportes/{endpoint}", headers=headers(uid)).status_code == 403
            )
    c.post(
        f"/ventas/{s['id']}/cancelar",
        headers=headers(1),
        json={"motivo": "Devolución", "reembolso_referencia": "DEV001"},
    )
    assert (
        c.get("/reportes/pagos?solo_confirmados=true", headers=headers(1)).json() == []
    )


def test_rollback_after_stock_change(security_client, security_db, headers):
    with patch(
        "app.modules.sales.service.finish_idempotency",
        side_effect=RuntimeError("secret-error"),
    ):
        r = post(
            security_client,
            headers,
            "/ventas",
            {"sucursal_id": 1, "productos": [{"producto_id": 1, "cantidad": 2}]},
        )
    assert r.status_code == 500 and "secret-error" not in r.text
    assert security_db.get(Inventory, 1).cantidad == 20
    for model in [Sale, InventoryMovement, IdempotencyRecord, CommercialEvent]:
        assert security_db.scalar(select(func.count()).select_from(model)) == 0


def test_html_escaping(security_client, security_db, headers):
    security_db.get(Product, 1).nombre = "<script>alert(1)</script>"
    security_db.commit()
    s = sale(security_client, headers)
    t = security_client.post(f"/tickets/venta/{s['id']}", headers=headers(2)).json()
    r = security_client.get(f"/tickets/{t['id']}/imprimir", headers=headers(2))
    assert "<script>" not in r.text and "&lt;script&gt;" in r.text


def test_nearest_and_no_fabricated_coordinates(security_client, security_db, headers):
    c = security_client
    assert (
        c.get("/sucursales-cercanas?latitud=20&longitud=-90", headers=headers(3)).json()
        == []
    )
    security_db.get(Branch, 1).latitud = 20
    security_db.get(Branch, 1).longitud = -90
    security_db.commit()
    r = c.get("/sucursales-cercanas?latitud=20&longitud=-90", headers=headers(3))
    assert r.status_code == 200, r.text
    assert r.json()[0]["distancia_km"] == 0
    assert (
        c.get(
            "/sucursales-cercanas?latitud=91&longitud=0", headers=headers(3)
        ).status_code
        == 422
    )
