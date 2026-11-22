from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.modules.administracion import images, imports, onboarding
from app.modules.administracion.common import reserve_code

from .conftest import headers
from .test_workflows import HIRE, PRODUCT, blob, scalar


@pytest.mark.parametrize("identifier", [1, 9, 99, 999, 9999, 10000, 99999, 100000])
@pytest.mark.parametrize("employee", [False, True])
def test_code_width(factory, identifier, employee):
    with factory.begin() as db:
        sequence = "empleados_id_seq" if employee else "productos_id_seq"
        db.execute(
            text("SELECT setval(CAST(:s AS regclass),:id,false)"),
            {"s": sequence, "id": identifier},
        )
        actual, code = reserve_code(db, employee)
        assert actual == identifier
        assert code == ("EMP-" if employee else "PROD-") + str(identifier).zfill(5)


def approved(api, factory):
    marker = uuid4().hex[:12]
    resp = api.post(
        "/administracion/empleados",
        headers=headers(key=marker),
        json={**HIRE, "email": marker + "@example.org"},
    )
    resp.raise_for_status()
    emp = resp.json()
    # El flujo completo de verificación y aprobación lo cubre test_employee_lifecycle.
    with factory.begin() as db:
        db.execute(
            text(
                "UPDATE gestion_interna.expediente SET estado='APROBADO' WHERE empleado_id=:id"
            ),
            {"id": emp["empleado_id"]},
        )
        db.execute(
            text("UPDATE empleados SET activo=true WHERE id=:id"),
            {"id": emp["empleado_id"]},
        )
        db.execute(
            text("UPDATE usuarios SET activo=true WHERE id=:id"),
            {"id": emp["usuario_id"]},
        )
    return emp


def test_revoke_live_session_and_atomicity(api, factory, monkeypatch):
    emp = approved(api, factory)
    identifier = emp["empleado_id"]
    jwt = headers(emp["usuario_id"])
    assert api.get("/auth/me", headers=jwt).is_success
    path = f"/administracion/solicitudes/{identifier}/decision"

    def revoke(key, uid=1):
        return api.post(
            path,
            headers=headers(uid, key),
            json={"accion": "revocar", "motivo": "Fin de asignación"},
        )

    assert revoke("sin-permiso", 2).status_code == 403
    assert (
        api.post(path, json={"accion": "revocar", "motivo": "Fin"}).status_code == 401
    )
    assert (
        api.post(
            path,
            headers=headers(key="invalid-key"),
            json={"accion": "correccion", "motivo": "x"},
        ).status_code
        == 409
    )

    def fail(*args):
        raise RuntimeError("fallo sintético de auditoría")

    with monkeypatch.context() as patch:
        patch.setattr(onboarding, "event", fail)
        with pytest.raises(RuntimeError):
            revoke("rollback-key")
    assert api.get("/auth/me", headers=jwt).is_success
    with ThreadPoolExecutor(2) as pool:
        assert all(
            r.is_success
            for r in pool.map(revoke, ["revocar-primera", "revocar-segunda"])
        )
    assert revoke("revocar-primera").is_success
    assert api.get("/auth/me", headers=jwt).status_code == 401
    assert api.get("/inventarios", headers=jwt).status_code == 401
    assert (
        api.patch(
            f"/usuarios/{emp['usuario_id']}/reactivar", headers=headers()
        ).status_code
        == 409
    )
    assert not scalar(
        factory, "SELECT activo FROM empleados WHERE id=:id", id=identifier
    )
    assert not scalar(
        factory, "SELECT activo FROM usuarios WHERE id=:id", id=emp["usuario_id"]
    )
    history = api.get(
        f"/administracion/solicitudes/{identifier}/historial", headers=headers()
    ).json()
    events = [e for e in history if e["accion"] == "REVOCADO"]
    assert (
        len(events) == 1
        and events[0]["actor_id"] == 1
        and events[0]["motivo"] == "Fin de asignación"
    )
    # Una nueva aprobación autorizada tampoco devuelve validez al JWT anterior.
    with factory.begin() as db:
        db.execute(
            text(
                "UPDATE gestion_interna.expediente SET estado='APROBADO' WHERE empleado_id=:id"
            ),
            {"id": identifier},
        )
        db.execute(
            text("UPDATE empleados SET activo=true WHERE id=:id"), {"id": identifier}
        )
        db.execute(
            text("UPDATE usuarios SET activo=true WHERE id=:id"),
            {"id": emp["usuario_id"]},
        )
    assert api.get("/auth/me", headers=jwt).status_code == 401


@pytest.mark.parametrize("size", [1000, 5000])
def test_import_resume_workers(factory, api, monkeypatch, size):
    data = "nombre,apellido,email,puesto,codigo_sucursal\n" + "\n".join(
        f"Nombre,Apellido,persona-{size}-{i}@example.org,Caja,C" for i in range(size)
    )
    url = "/administracion/importaciones"
    batch = api.post(
        url + "/vista-previa",
        files={"archivo": ("plantilla.csv", data)},
        headers=headers(),
    ).json()
    identifier = batch["id"]
    api.post(f"{url}/{identifier}/confirmar", headers=headers()).raise_for_status()
    original = imports.hire

    def interrupted(db, data, actor):
        if data.email.endswith("-3@example.org"):
            raise RuntimeError("interrupción local")
        return original(db, data, actor)

    with monkeypatch.context() as patch:
        patch.setattr(imports, "hire", interrupted)
        with factory() as db, pytest.raises(RuntimeError):
            imports.process_chunk(db)
    assert (
        scalar(
            factory,
            "select count(*) from usuarios where email like :pattern",
            pattern=f"persona-{size}-%",
        )
        == 0
    )

    def drain(_):
        with factory() as db:
            while imports.process_chunk(db):
                pass

    with ThreadPoolExecutor(2) as pool:
        list(pool.map(drain, range(2)))
    result = api.get(f"{url}/{identifier}", headers=headers()).json()
    assert (
        result["estado"] == "TERMINADO"
        and len({r["empleado_id"] for r in result["filas"]}) == size
    )
    assert (
        api.post(f"{url}/{identifier}/confirmar", headers=headers()).json()["estado"]
        == "TERMINADO"
    )


def test_transfer_and_photo_concurrency(api, factory, monkeypatch):
    from app.core.config import settings
    from app.modules.users.model import User

    with factory.begin() as db:
        second = User(
            nombre="Admin",
            apellido="Dos",
            email="admin2@example.org",
            rol_id=1,
            password_hash="!",
            activo=True,
        )
        db.add(second)
        db.flush()
        other = second.id
    result = api.post(
        "/administracion/productos",
        json=PRODUCT,
        headers=headers(key="alta-concurrencia"),
    ).json()
    initial = result["inventarios"]

    def transfer(args):
        i, actor = args
        return api.post(
            f"/inventario-operativo/{initial[i]['id']}/movimiento",
            headers=headers(actor, "traspaso-inverso"),
            json={
                "tipo": "traspaso",
                "sucursal_destino_id": initial[1 - i]["sucursal_id"],
                "cantidad": 3,
            },
        )

    with ThreadPoolExecutor(2) as pool:
        for r in pool.map(transfer, [(0, 1), (1, other)]):
            r.raise_for_status()
    for i in initial:
        assert (
            scalar(factory, "SELECT cantidad FROM inventarios WHERE id=:i", i=i["id"])
            == i["cantidad"]
        )
    monkeypatch.setattr(settings, "supabase_url", "https://simulado.example.org")
    monkeypatch.setattr(settings, "supabase_storage_key", "solo-pruebas")
    monkeypatch.setattr(images, "storage", lambda *args: None)
    product = result["producto"]["id"]

    def replace(actor):
        return api.put(
            f"/administracion/productos/{product}/imagen",
            headers=headers(actor, "foto-concurrente"),
            files={"archivo": ("foto.png", blob("PNG"), "image/png")},
        )

    with ThreadPoolExecutor(2) as pool:
        for r in pool.map(replace, [1, other]):
            r.raise_for_status()
    assert (
        scalar(
            factory,
            "SELECT count(*) FROM producto_imagenes WHERE producto_id=:i AND es_principal",
            i=product,
        )
        == 1
    )
    assert (
        scalar(
            factory,
            "SELECT count(*) FROM gestion_interna.objeto WHERE producto_id=:i AND estado='RETIRADO'",
            i=product,
        )
        == 1
    )


@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/administracion/productos"),
        ("post", "/administracion/productos/con-imagen"),
        ("put", "/administracion/productos/1/imagen"),
        ("delete", "/administracion/productos/1/imagenes/1"),
        ("post", "/administracion/empleados"),
        ("post", "/administracion/solicitudes/1/decision"),
        ("get", "/administracion/solicitudes/1/historial"),
        ("post", "/administracion/importaciones/vista-previa"),
        ("post", "/administracion/importaciones/1/confirmar"),
        ("get", "/administracion/importaciones/1"),
        ("get", "/administracion/importaciones/1/errores.csv"),
        ("put", "/administracion/identidad"),
        ("post", "/administracion/beneficios"),
        ("put", "/administracion/beneficios/1"),
    ],
)
def test_administrative_boundaries(api, method, path):
    for uid in (2, 3):
        assert (
            api.request(method, path, headers=headers(uid, "role-boundary")).status_code
            == 403
        )


def test_ambiguous_provider_acknowledgement(api, factory, monkeypatch):
    import httpx

    from app.core.config import settings
    from app.modules.administracion import mail

    emp = api.post(
        "/administracion/empleados",
        json={**HIRE, "email": "ambiguous@example.org"},
        headers=headers(key="ambiguous-mail"),
    ).json()
    identifier = emp["empleado_id"]
    monkeypatch.setattr(settings, "resend_api_key", "test")
    monkeypatch.setattr(settings, "correo_remitente", "demo@example.org")
    monkeypatch.setattr(
        mail.httpx, "post", lambda *a, **kw: httpx.Response(200, json={"id": None})
    )
    with factory.begin() as db:
        db.execute(
            text(
                "UPDATE gestion_interna.correo SET proximo=now()+interval '1 day' WHERE empleado_id<>:id"
            ),
            {"id": identifier},
        )
    with factory() as db:
        assert mail.dispatch_one(db)
    assert (
        scalar(
            factory,
            "SELECT estado FROM gestion_interna.correo WHERE empleado_id=:id",
            id=identifier,
        )
        == "CONCILIAR"
    )


def test_role_assignment_uses_confirmed_catalog(api, factory):
    from app.core.roles import RoleID, catalog_role_active

    response = api.post(
        "/administracion/empleados",
        headers=headers(key="catalogo-valido"),
        json={**HIRE, "email": "alta-catalogo@example.org"},
    )
    assert response.status_code in (200, 201), response.text
    with factory() as db:
        assert all(catalog_role_active(db, role) for role in RoleID)
        assert (
            db.scalar(
                text("""SELECT r.nombre FROM usuarios u JOIN roles r ON r.id=u.rol_id
                                WHERE u.id=:id"""),
                {"id": response.json()["usuario_id"]},
            )
            == "Empleado"
        )


@pytest.mark.parametrize("condition", ["ausente", "inactivo", "nombre_incompatible"])
def test_employee_role_anomaly_prevents_hire(factory, condition):
    from fastapi import HTTPException

    from app.core.auth import validate_active_role
    from app.core.roles import RoleID, catalog_role_active

    # Cada anomalía vive en una transacción privada. La FK del personal existente se conserva.
    with factory() as db:
        if condition == "ausente":
            # La FK sigue apuntando al catálogo original. El rollback restituye su nombre.
            db.execute(
                text("ALTER TABLE public.roles RENAME TO roles_fixture_original")
            )
            db.execute(
                text(
                    "CREATE TABLE public.roles (id bigint, nombre text, activo boolean)"
                )
            )
        elif condition == "inactivo":
            db.execute(text("UPDATE roles SET activo=false WHERE id=2"))
        else:
            db.execute(text("UPDATE roles SET nombre='Cliente' WHERE id=2"))
        assert catalog_role_active(db, RoleID.EMPLEADO) is not True
        with pytest.raises(HTTPException) as denied:
            validate_active_role(db, RoleID.EMPLEADO)
        assert denied.value.status_code == 403
        data = onboarding.Hire(**{**HIRE, "email": "rol-anomalo@example.org"})
        with pytest.raises(HTTPException) as unavailable:
            onboarding.hire(db, data, 1)
        assert unavailable.value.status_code == 503
        assert (
            db.scalar(
                text("SELECT count(*) FROM usuarios WHERE email=:email"),
                {"email": data.email},
            )
            == 0
        )


def test_managed_trigger_validates_catalog_but_allows_deactivation(api, factory):
    from sqlalchemy.exc import IntegrityError

    emp = approved(api, factory)
    with factory() as db:
        db.execute(text("UPDATE roles SET activo=false WHERE id=2"))
        db.execute(
            text("UPDATE usuarios SET activo=false WHERE id=:u"),
            {"u": emp["usuario_id"]},
        )
        with pytest.raises(IntegrityError) as error, db.begin_nested():
            db.execute(
                text("UPDATE usuarios SET activo=true WHERE id=:u"),
                {"u": emp["usuario_id"]},
            )
        assert error.value.orig.sqlstate == "23514"


@pytest.mark.parametrize("active,name", [(False, "Administrador"), (True, "Empleado")])
def test_bootstrap_rejects_invalid_admin_catalog(factory, monkeypatch, active, name):
    from scripts import bootstrap_admin

    with factory() as db:
        db.execute(
            text("UPDATE roles SET activo=:active,nombre=:name WHERE id=1"),
            {"active": active, "name": name},
        )
        answers = iter(["Nombre", "Prueba", "bootstrap@example.org", "CREAR ADMIN"])
        monkeypatch.setattr("builtins.input", lambda _: next(answers))
        monkeypatch.setattr(bootstrap_admin, "getpass", lambda _: "SoloPruebaLocal123")
        monkeypatch.setattr(bootstrap_admin, "SessionLocal", lambda: db)
        with pytest.raises(SystemExit, match="rol Administrador no está disponible"):
            bootstrap_admin.main()


def test_import_reports_existing_email(api):
    url = "/administracion/importaciones/vista-previa"
    payload = "nombre,apellido,email,puesto,codigo_sucursal\nNombre,Prueba,ADMIN@example.org,Caja,C"
    response = api.post(
        url, headers=headers(), files={"archivo": ("personas.csv", payload)}
    )
    assert response.status_code == 200
    row = response.json()["filas"][0]
    assert row["estado"] == "ERROR" and "registrado" in row["error"]


def test_image_reencoding_removes_source_profile():
    from io import BytesIO

    from PIL import Image

    raw = BytesIO()
    Image.new("RGB", (2, 2)).save(raw, format="PNG", icc_profile=b"metadata-de-prueba")
    encoded, suffix, mime = images.validate_image(raw.getvalue(), "image/png")
    with Image.open(BytesIO(encoded)) as img:
        assert (img.size, suffix, mime) == ((2, 2), "png", "image/png")
        assert "icc_profile" not in img.info


@pytest.mark.parametrize("iat", [None, "123456789", True])
def test_jwt_requires_numeric_emission_time(iat):
    from app.core.jwt import TokenValidationError, verified_claims
    from tests.core.test_jwt import sign_token, valid_payload

    with pytest.raises(TokenValidationError):
        verified_claims(sign_token({**valid_payload(), "iat": iat}))


def test_reinvitation_requires_fresh_approval_and_login(api, factory, monkeypatch):
    import re

    from app.api.routes.auth import get_rate_limit_session_factory

    from .test_workflows import latest

    monkeypatch.setitem(
        api.app.dependency_overrides, get_rate_limit_session_factory, lambda: factory
    )
    email = "reincorporacion@example.org"
    credentials = {"email": email, "password": "PruebaIntegral12345"}
    api.put(
        "/administracion/identidad",
        headers=headers(),
        json={
            "nombre": "Ensayo",
            "mensaje": "Bienvenido",
            "firma": "Equipo",
            "color": "#123456",
            "contacto": "Oficina",
        },
    ).raise_for_status()
    case = api.post(
        "/administracion/empleados",
        headers=headers(key="reinvitacion-alta"),
        json={**HIRE, "email": email},
    ).json()["empleado_id"]
    url = f"/administracion/solicitudes/{case}/decision"

    def decision(action, key):
        result = api.post(
            url, headers=headers(key=key), json={"accion": action, "motivo": "Ensayo"}
        )
        result.raise_for_status()
        return result.json()["estado"]

    def submit():
        token = re.search(
            r"token=([A-Za-z0-9_-]+)", latest(factory, case, "invitacion")
        )[1]
        api.post("/incorporacion/codigo", json={"token": token}).raise_for_status()
        otp = re.search(r"<p>(\d{6})</p>", latest(factory, case, "codigo"))[1]
        api.post(
            "/incorporacion/solicitud",
            json={
                "token": token,
                "codigo": otp,
                "nombre": "Prueba",
                "apellido": "Local",
                "password": credentials["password"],
            },
        ).raise_for_status()
        return token

    old_invite = submit()
    assert decision("aprobar", "primera-aprobacion") == "APROBADO"
    old_jwt = api.post("/auth/login", json=credentials).json()["access_token"]
    assert decision("revocar", "revocacion-real") == "REVOCADO"
    assert api.post("/auth/login", json=credentials).status_code == 401
    assert decision("reinvitar", "segunda-invitacion") == "INVITADO"
    assert (
        api.post("/incorporacion/codigo", json={"token": old_invite}).status_code == 400
    )
    assert submit() != old_invite
    assert api.post("/auth/login", json=credentials).status_code == 401
    assert decision("aprobar", "segunda-aprobacion") == "APROBADO"
    assert (
        api.get("/auth/me", headers={"Authorization": "Bearer " + old_jwt}).status_code
        == 401
    )
    # El emisor existente tiene precisión de segundos. Esperar el siguiente segundo en la BD de prueba.
    with factory() as db:
        db.execute(text("SELECT pg_sleep(1.05)"))
    current = api.post("/auth/login", json=credentials).json()["access_token"]
    assert (
        api.get("/auth/me", headers={"Authorization": "Bearer " + current}).status_code
        == 200
    )
