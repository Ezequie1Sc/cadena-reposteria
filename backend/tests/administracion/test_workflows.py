import io
import json
import re
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from openpyxl import Workbook
from PIL import Image
from sqlalchemy import text

from app.core.config import settings
from app.modules.administracion import images, imports, mail

from .conftest import headers

PRODUCT = {
    "nombre": "Concha",
    "categoria_id": 1,
    "precio": "12.50",
    "inventarios": [
        {"sucursal_id": 1, "existencias_iniciales": 50, "stock_minimo": 15},
        {"sucursal_id": 2, "existencias_iniciales": 80, "stock_minimo": 80},
    ],
}
HIRE = {
    "nombre": "Test",
    "apellido": "Alta",
    "email": "alta@example.org",
    "puesto": "Caja",
    "sucursal_id": 1,
}


def scalar(factory, s, **params):
    with factory() as db:
        return db.execute(text(s), params).scalar_one()


def test_catalog_atomic_replay_and_roles(api, factory):
    path = "/administracion/productos"
    assert api.post(path, json=PRODUCT).status_code == 401
    assert (
        api.post(path, headers=headers(2, "employee-key"), json=PRODUCT).status_code
        == 403
    )
    count = scalar(factory, "select count(*) from productos")
    bad = {
        **PRODUCT,
        "inventarios": [
            *PRODUCT["inventarios"],
            {"sucursal_id": 999, "existencias_iniciales": 1, "stock_minimo": 0},
        ],
    }
    assert (
        api.post(path, headers=headers(key="rollback-key"), json=bad).status_code == 422
    )
    assert scalar(factory, "select count(*) from productos") == count

    def post(key):
        r = api.post(path, json=PRODUCT, headers=headers(key=key))
        assert r.status_code == 201, r.text
        return r.json()

    with ThreadPoolExecutor(2) as pool:
        a, b = pool.map(post, ["same-product-key"] * 2)
    assert a == b
    product = a["producto"]
    assert product["sku"] == f"PROD-{product['id']:05d}"
    assert [i["cantidad"] for i in a["inventarios"]] == [50, 80]
    inv = a["inventarios"][1]["id"]
    assert (
        api.post(
            f"/inventario-operativo/{inv}/movimiento",
            headers=headers(2, "branch-key"),
            json={"tipo": "entrada", "cantidad": 10},
        ).status_code
        == 403
    )
    for _ in range(2):
        r = api.post(
            f"/inventario-operativo/{inv}/movimiento",
            headers=headers(key="entry-key"),
            json={"tipo": "entrada", "cantidad": 10},
        )
        assert r.status_code == 200, r.text
    assert (
        scalar(factory, "select cantidad from inventarios where id=:id", id=inv) == 90
    )
    assert (
        api.patch(
            "/productos/" + str(product["id"]), headers=headers(), json={"sku": "x"}
        ).status_code
        == 409
    )
    assert (
        api.post(
            path,
            headers=headers(key="same-product-key"),
            json={**PRODUCT, "nombre": "Otro"},
        ).status_code
        == 409
    )


def blob(fmt):
    stream = io.BytesIO()
    Image.new("RGB", (10, 10)).save(stream, format=fmt)
    return stream.getvalue()


@pytest.mark.parametrize(
    "fmt,mime", [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")]
)
def test_image_validation(fmt, mime):
    data = blob(fmt)
    assert images.validate_image(data, mime)[2] == mime
    with pytest.raises(Exception) as error:
        images.validate_image(data, "application/pdf")
    assert error.value.status_code == 415
    assert (
        images.validate_image(data + b" " * (images.MAX_BYTES - len(data)), mime)[2]
        == mime
    )
    with pytest.raises(Exception) as error:
        images.validate_image(data + b" " * images.MAX_BYTES, mime)
    assert error.value.status_code == 413


def test_image_lifecycle(api, factory, monkeypatch):
    monkeypatch.setattr(settings, "supabase_url", "https://storage.example.org")
    monkeypatch.setattr(settings, "supabase_storage_key", "test-only")
    objects = {}

    def storage(method, key, content=None, mime=None):
        if method == "POST":
            objects[key] = content
        else:
            objects.pop(key, None)

    monkeypatch.setattr(images, "storage", storage)
    files = {"archivo": ("foto.png", blob("PNG"), "image/png")}
    result = api.post(
        "/administracion/productos/con-imagen",
        data={"datos": json.dumps(PRODUCT)},
        files=files,
        headers=headers(key="multipart-key"),
    )
    assert result.status_code == 201, result.text
    prod = result.json()["producto_id"]
    path = f"/administracion/productos/{prod}/imagen"
    assert (
        api.put(path, files=files, headers=headers(2, "unauthorised")).status_code
        == 403
    )
    result = api.put(path, files=files, headers=headers(key="replace-key"))
    assert result.status_code == 200, result.text
    image_id = result.json()["imagen_id"]
    assert (
        api.delete(
            f"/administracion/productos/{prod + 100}/imagenes/{image_id}",
            headers=headers(),
        ).status_code
        == 404
    )
    assert api.delete(
        f"/administracion/productos/{prod}/imagenes/{image_id}", headers=headers()
    ).is_success
    with factory() as db:
        db.execute(text("UPDATE gestion_interna.objeto SET revisar=now()"))
        db.commit()
        while images.clean_one(db):
            pass
    assert not objects

    def failed(*args, **kwargs):
        from fastapi import HTTPException

        raise HTTPException(503, "simulado")

    monkeypatch.setattr(images, "storage", failed)
    count = scalar(factory, "select count(*) from productos")
    assert (
        api.post(
            "/administracion/productos/con-imagen",
            data={"datos": json.dumps(PRODUCT)},
            files=files,
            headers=headers(key="failure-key"),
        ).status_code
        == 503
    )
    assert scalar(factory, "select count(*) from productos") == count


def latest(factory, identifier, kind):
    body = scalar(
        factory,
        "SELECT contenido FROM gestion_interna.correo WHERE empleado_id=:id AND tipo=:kind ORDER BY creado DESC LIMIT 1",
        id=identifier,
        kind=kind,
    )
    return json.loads(mail.cipher().decrypt(bytes(body)))["html"]


def test_employee_lifecycle(api, factory, monkeypatch):
    def post(url, data, key="onboard-key", uid=1):
        return api.post(url, json=data, headers=headers(uid, key))

    path = "/administracion/empleados"
    a = post(path, HIRE)
    assert a.status_code == 201, a.text
    emp = a.json()
    identifier = emp["empleado_id"]
    uid = emp["usuario_id"]
    assert post(path, HIRE).json() == emp
    assert emp["numero_empleado"] == f"EMP-{identifier:05d}"
    assert api.patch(f"/usuarios/{uid}/reactivar", headers=headers()).status_code == 409
    url = f"/administracion/solicitudes/{identifier}/decision"
    assert post(url, {"accion": "aprobar"}).status_code == 409
    assert post(url, {"accion": "aprobar"}, uid=2).status_code == 403
    token = re.search(
        "token=([A-Za-z0-9_-]+)", latest(factory, identifier, "invitacion")
    )[1]
    assert api.post("/incorporacion/codigo", json={"token": token}).status_code == 202
    assert api.post("/incorporacion/codigo", json={"token": token}).status_code == 429
    otp = re.search(r"<p>(\d{6})</p>", latest(factory, identifier, "codigo"))[1]
    data = dict(
        token=token,
        codigo=otp,
        nombre="Ana",
        apellido="Prueba",
        password="Prueba12345678",
    )
    assert (
        api.post(
            "/incorporacion/solicitud",
            json={**data, "codigo": "000000" if otp != "000000" else "111111"},
        ).status_code
        == 400
    )
    assert api.post("/incorporacion/solicitud", json=data).is_success
    assert api.post("/incorporacion/solicitud", json=data).status_code == 400
    assert api.get("/auth/me", headers=headers(uid)).status_code == 401
    identity = dict(
        nombre="Prueba",
        mensaje="Hola",
        firma="Equipo",
        color="#123456",
        contacto="Oficina",
    )
    assert api.put(
        "/administracion/identidad", json=identity, headers=headers()
    ).is_success
    assert post(
        "/administracion/beneficios",
        {"nombre": "Configurado", "condiciones": "Prueba", "sucursal_id": 1},
    ).is_success
    assert post(
        "/administracion/beneficios",
        {"nombre": "Otra sede", "condiciones": "", "sucursal_id": 2},
    ).is_success
    with ThreadPoolExecutor(2) as pool:
        assert all(
            r.is_success
            for r in pool.map(lambda _: post(url, {"accion": "aprobar"}), range(2))
        )
    assert (
        scalar(
            factory,
            "select count(*) from gestion_interna.correo where empleado_id=:id and tipo='bienvenida'",
            id=identifier,
        )
        == 1
    )
    welcome = api.get("/empleado/bienvenida", headers=headers(uid)).json()
    assert welcome["pendiente"] and [b["nombre"] for b in welcome["beneficios"]] == [
        "Configurado"
    ]
    assert api.post("/empleado/bienvenida/vista", headers=headers(uid)).is_success
    assert not api.get("/empleado/bienvenida", headers=headers(uid)).json()["pendiente"]
    monkeypatch.setattr(settings, "resend_api_key", "test-only")
    monkeypatch.setattr(settings, "correo_remitente", "pruebas@example.org")
    sent = []

    def transport(url, **kw):
        sent.append(kw["headers"]["Idempotency-Key"])
        return httpx.Response(200, json={"id": "simulado"})

    monkeypatch.setattr(mail.httpx, "post", transport)
    with factory() as db:
        while mail.dispatch_one(db):
            pass
    assert len(set(sent)) == len(sent) >= 3


@pytest.mark.parametrize("suffix", ["csv", "xlsx"])
def test_import(api, factory, suffix):
    records = [list(imports.HEADERS)] + [
        ["Nombre", "Prueba", f"lote-{suffix}-{i}@example.org", "Caja", "C"]
        for i in range(401)
    ]
    records.extend(
        [records[-1], ["A", "B", "mala@example.org", "Caja", "SIN-SUCURSAL"]]
    )
    if suffix == "csv":
        content = "\n".join(",".join(r) for r in records).encode()
    else:
        book = Workbook()
        for r in records:
            book.active.append(r)
        buf = io.BytesIO()
        book.save(buf)
        content = buf.getvalue()
    url = "/administracion/importaciones"
    files = {"archivo": ("empleados." + suffix, content)}
    r = api.post(url + "/vista-previa", headers=headers(), files=files)
    assert r.is_success, r.text
    identifier = r.json()["id"]
    assert (
        api.post(url + "/vista-previa", headers=headers(), files=files).json()["id"]
        == identifier
    )
    assert api.post(f"{url}/{identifier}/confirmar", headers=headers()).is_success
    with factory() as db:
        while imports.process_chunk(db):
            pass
    result = api.get(f"{url}/{identifier}", headers=headers()).json()
    assert result["estado"] == "TERMINADO"
    assert sum(i["estado"] == "CREADA" for i in result["filas"]) == 401
    assert (
        len(
            api.get(
                f"{url}/{identifier}/errores.csv", headers=headers()
            ).text.splitlines()
        )
        == 3
    )
    assert (
        api.post(f"{url}/{identifier}/confirmar", headers=headers()).json()["estado"]
        == "TERMINADO"
    )


@pytest.mark.parametrize("action", ["rechazar", "correccion", "revocar"])
def test_decision_invalidates_credentials(api, factory, action):
    data = {**HIRE, "email": action + "@example.org"}
    emp = api.post(
        "/administracion/empleados", headers=headers(key="alta-" + action), json=data
    ).json()
    identifier = emp["empleado_id"]
    token = re.search(
        "token=([A-Za-z0-9_-]+)", latest(factory, identifier, "invitacion")
    )[1]
    api.post("/incorporacion/codigo", json={"token": token}).raise_for_status()
    otp = re.search(r"<p>(\d{6})</p>", latest(factory, identifier, "codigo"))[1]
    proof = api.post(
        "/incorporacion/verificar", json={"token": token, "codigo": otp}
    ).json()["comprobante"]
    assert (
        api.post(
            "/incorporacion/verificar", json={"token": token, "codigo": otp}
        ).status_code
        == 400
    )
    form = dict(
        token=token, codigo=proof, nombre="N", apellido="A", password="Usuario123456789"
    )
    api.post("/incorporacion/solicitud", json=form).raise_for_status()
    url = f"/administracion/solicitudes/{identifier}/decision"
    result = api.post(
        url,
        headers=headers(key="decision-" + action),
        json={"accion": action, "motivo": "Revisión"},
    )
    assert result.is_success, result.text
    assert api.post("/incorporacion/solicitud", json=form).status_code == 400
    assert api.get("/auth/me", headers=headers(emp["usuario_id"])).status_code == 401
    assert (
        api.patch(f"/empleados/{identifier}/reactivar", headers=headers()).status_code
        == 409
    )


def test_code_limits_and_expiry(api, factory):
    from app.modules.administracion.onboarding import digest

    data = {**HIRE, "email": "caducidad@example.org"}
    emp = api.post(
        "/administracion/empleados", headers=headers(key="alta-caducidad"), json=data
    ).json()
    identifier = emp["empleado_id"]
    token = re.search(
        "token=([A-Za-z0-9_-]+)", latest(factory, identifier, "invitacion")
    )[1]
    for _ in range(5):
        assert (
            api.post(
                "/incorporacion/verificar", json={"token": token, "codigo": "000000"}
            ).status_code
            == 400
        )
    assert api.post("/incorporacion/codigo", json={"token": token}).status_code == 429
    with factory.begin() as db:
        db.execute(
            text(
                "UPDATE gestion_interna.expediente SET vence=now() WHERE token_hash=:h"
            ),
            {"h": digest(token)},
        )
    assert api.post("/incorporacion/codigo", json={"token": token}).status_code == 400


def test_distinct_parallel_products_and_large_id(api, factory):
    with factory.begin() as db:
        db.execute(text("SELECT setval('productos_id_seq',10000)"))

    def create(key):
        r = api.post(
            "/administracion/productos", json=PRODUCT, headers=headers(key=key)
        )
        r.raise_for_status()
        return r.json()["producto"]

    with ThreadPoolExecutor(2) as pool:
        products = list(pool.map(create, ["parallel-first", "parallel-second"]))
    assert products[0]["id"] != products[1]["id"]
    assert all(p["sku"] == "PROD-" + str(p["id"]) for p in products)


def test_resend_transient_retry_and_expired_window(api, factory, monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "fake")
    monkeypatch.setattr(settings, "correo_remitente", "test@example.org")
    # Datos sintéticos de una única invitación para esta prueba.
    with factory.begin() as db:
        db.execute(
            text(
                "UPDATE gestion_interna.correo SET estado='CANCELADO' WHERE estado='LISTO'"
            )
        )
    emp = api.post(
        "/administracion/empleados",
        headers=headers(key="alta-transporte"),
        json={**HIRE, "email": "retry@example.org"},
    ).json()
    calls = []

    def transport(url, **kwargs):
        calls.append(kwargs["headers"]["Idempotency-Key"])
        return httpx.Response(503)

    monkeypatch.setattr(mail.httpx, "post", transport)
    with factory() as db:
        assert mail.dispatch_one(db)
        db.execute(
            text(
                "UPDATE gestion_interna.correo SET proximo=now() WHERE empleado_id=:i"
            ),
            {"i": emp["empleado_id"]},
        )
        db.commit()
        assert mail.dispatch_one(db)
        assert len(calls) == 2 and calls[0] == calls[1]
        db.execute(
            text(
                "UPDATE gestion_interna.correo SET creado=now()-interval '25 hours',proximo=now() WHERE empleado_id=:i"
            ),
            {"i": emp["empleado_id"]},
        )
        db.commit()
        assert mail.dispatch_one(db)
        assert len(calls) == 2
    assert (
        scalar(
            factory,
            "SELECT estado FROM gestion_interna.correo WHERE empleado_id=:i",
            i=emp["empleado_id"],
        )
        == "CONCILIAR"
    )


def test_database_backstop_and_historical_conflict(api, factory):
    from sqlalchemy.exc import IntegrityError

    hire = api.post(
        "/administracion/empleados",
        headers=headers(key="old-app-guard"),
        json={**HIRE, "email": "guard@example.org"},
    ).json()
    with pytest.raises(IntegrityError), factory.begin() as db:
        db.execute(
            text("UPDATE usuarios SET activo=true WHERE id=:id"),
            {"id": hire["usuario_id"]},
        )
    # El caso sintético conserva una matrícula asociada a otro ID.
    with factory.begin() as db:
        db.execute(
            text("UPDATE empleados SET numero_empleado='EMP-10000' WHERE usuario_id=2")
        )
        db.execute(text("SELECT setval('empleados_id_seq',10000,false)"))
    r = api.post(
        "/administracion/empleados",
        headers=headers(key="collision-legacy"),
        json={**HIRE, "email": "conflicto@example.org"},
    )
    assert r.status_code == 409
    assert (
        scalar(factory, "select numero_empleado from empleados where usuario_id=2")
        == "EMP-10000"
    )
    assert (
        scalar(
            factory, "select count(*) from usuarios where email='conflicto@example.org'"
        )
        == 0
    )
    r = api.post(
        "/administracion/empleados",
        headers=headers(key="collision-legacy"),
        json={**HIRE, "email": "conflicto@example.org"},
    )
    assert r.json()["numero_empleado"] == "EMP-10001"


def test_orphan_after_database_failure(api, factory, monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setattr(settings, "supabase_url", "https://storage.example.org")
    monkeypatch.setattr(settings, "supabase_storage_key", "test-only")
    stored = set()

    def transport(method, key, *args):
        if method == "POST":
            stored.add(key)
        else:
            stored.discard(key)

    monkeypatch.setattr(images, "storage", transport)

    def failure(db, product):
        raise HTTPException(503, "Fallo simulado después de subir")

    monkeypatch.setattr(images, "retire", failure)
    r = api.post(
        "/administracion/productos/con-imagen",
        data={"datos": json.dumps(PRODUCT)},
        files={"archivo": ("x.png", blob("PNG"), "image/png")},
        headers=headers(key="database-failure"),
    )
    assert r.status_code == 503 and len(stored) == 1
    with factory() as db:
        db.execute(
            text(
                "UPDATE gestion_interna.objeto SET revisar=now() WHERE estado='PREPARADO'"
            )
        )
        db.commit()
        while images.clean_one(db):
            pass
    assert not stored


def test_storage_http_contract(monkeypatch):
    monkeypatch.setattr(settings, "supabase_url", "https://test.example.org")
    monkeypatch.setattr(settings, "supabase_storage_key", "sb_secret_fake")
    requests = []

    def fake(method, url, **kwargs):
        requests.append((method, url, kwargs))
        return httpx.Response(200, json=[], request=httpx.Request(method, url))

    monkeypatch.setattr(images.httpx, "request", fake)
    key = "catalogo/" + "1" * 32 + ".webp"
    images.storage("POST", key, b"test", "image/webp")
    images.storage("DELETE", key)
    assert requests[0][1].endswith("/object/productos/" + key)
    assert requests[1][2]["json"] == {"prefixes": [key]}
    assert "Authorization" not in requests[0][2]["headers"]
