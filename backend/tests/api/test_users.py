
"""Pruebas HTTP del CRUD administrativo de usuarios."""

import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.jwt import create_access_token
from app.core.security import hash_password, verify_password
from app.db.session import Base, get_db
from app.main import app
from app.modules.users.model import User
from app.shared.models.role_reference import roles_reference


PASSWORD = "PasswordSegura2026!"
NEW_PASSWORD = "NuevaPasswordSegura2026!"


@pytest.fixture
def db():
    """Crea una base SQLite independiente por prueba."""

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(
        engine,
        tables=[roles_reference, User.__table__],
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
            email=f"rol{role_id}@example.com",
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


def auth_headers(user):
    """Genera un JWT válido para el usuario indicado."""

    token = create_access_token(user.id)

    return {
        "Authorization": f"Bearer {token}",
    }


def new_user_payload(email="nuevo@example.com"):
    """Construye una solicitud válida de registro."""

    return {
        "rol_id": 3,
        "nombre": "María",
        "apellido": "García",
        "email": email,
        "telefono": "9991234567",
        "password": PASSWORD,
    }


# ============================================================
# AUTORIZACIÓN
# ============================================================


@pytest.mark.parametrize(
    "method,path,payload",
    [
        ("GET", "/usuarios", None),
        ("GET", "/usuarios/1", None),
        ("POST", "/usuarios", new_user_payload()),
        ("PATCH", "/usuarios/1", {"nombre": "Cambio"}),
        ("DELETE", "/usuarios/1", None),
        ("PATCH", "/usuarios/1/reactivar", None),
    ],
)
def test_routes_require_authentication(
    client,
    method,
    path,
    payload,
):
    """Ninguna operación administrativa permite acceso anónimo."""

    response = client.request(
        method,
        path,
        json=payload,
    )

    assert response.status_code == 401


@pytest.mark.parametrize("role_id", [2, 3])
@pytest.mark.parametrize(
    "method,path,payload",
    [
        ("GET", "/usuarios", None),
        ("GET", "/usuarios/1", None),
        ("POST", "/usuarios", new_user_payload()),
        ("PATCH", "/usuarios/1", {"nombre": "Cambio"}),
        ("DELETE", "/usuarios/1", None),
        ("PATCH", "/usuarios/1/reactivar", None),
    ],
)
def test_non_admin_cannot_access_user_routes(
    client,
    users,
    role_id,
    method,
    path,
    payload,
):
    """Empleados y clientes no pueden administrar usuarios."""

    response = client.request(
        method,
        path,
        headers=auth_headers(users[role_id]),
        json=payload,
    )

    assert response.status_code == 403


def test_invalid_token_returns_401(client):
    """Un token inválido no permite consultar usuarios."""

    response = client.get(
        "/usuarios",
        headers={
            "Authorization": "Bearer token-invalido",
        },
    )

    assert response.status_code == 401


def test_inactive_admin_returns_401(client, db, users):
    """Un administrador desactivado pierde acceso."""

    admin = users[1]
    admin.activo = False
    db.commit()

    response = client.get(
        "/usuarios",
        headers=auth_headers(admin),
    )

    assert response.status_code == 401


def test_inactive_admin_role_returns_403(client, db, users):
    """Un rol desactivado no autoriza operaciones."""

    db.execute(
        text("UPDATE roles SET activo = 0 WHERE id = 1")
    )
    db.commit()

    response = client.get(
        "/usuarios",
        headers=auth_headers(users[1]),
    )

    assert response.status_code == 403


# ============================================================
# CREACIÓN
# ============================================================


def test_admin_can_create_user(client, users):
    """Un administrador puede registrar usuarios."""

    response = client.post(
        "/usuarios",
        headers=auth_headers(users[1]),
        json=new_user_payload(),
    )

    assert response.status_code == 201

    body = response.json()

    assert body["email"] == "nuevo@example.com"
    assert body["nombre"] == "María"
    assert body["rol_id"] == 3
    assert body["activo"] is True
    assert isinstance(body["id"], int)


def test_created_user_password_is_hashed(client, db, users):
    """La contraseña se almacena como hash Argon2id."""

    response = client.post(
        "/usuarios",
        headers=auth_headers(users[1]),
        json=new_user_payload(),
    )

    assert response.status_code == 201

    created = db.get(User, response.json()["id"])

    assert created is not None
    assert created.password_hash != PASSWORD
    assert verify_password(PASSWORD, created.password_hash)


def test_create_user_does_not_expose_password(client, users):
    """La respuesta nunca devuelve contraseñas."""

    response = client.post(
        "/usuarios",
        headers=auth_headers(users[1]),
        json=new_user_payload(),
    )

    assert response.status_code == 201

    body = response.json()

    assert "password" not in body
    assert "password_hash" not in body


def test_create_duplicate_email_returns_409(client, users):
    """No se permiten correos duplicados."""

    payload = new_user_payload(
        email="rol2@example.com",
    )

    response = client.post(
        "/usuarios",
        headers=auth_headers(users[1]),
        json=payload,
    )

    assert response.status_code == 409


def test_create_invalid_role_returns_422(client, users):
    """No se permite asignar un rol inexistente."""

    payload = new_user_payload()
    payload["rol_id"] = 999

    response = client.post(
        "/usuarios",
        headers=auth_headers(users[1]),
        json=payload,
    )

    assert response.status_code == 422


def test_create_inactive_role_returns_422(
    client,
    db,
    users,
):
    """No se permite asignar un rol inactivo."""

    db.execute(
        text("UPDATE roles SET activo = 0 WHERE id = 3")
    )
    db.commit()

    response = client.post(
        "/usuarios",
        headers=auth_headers(users[1]),
        json=new_user_payload(),
    )

    assert response.status_code == 422


def test_create_short_password_returns_422(client, users):
    """Las contraseñas deben cumplir la longitud mínima."""

    payload = new_user_payload()
    payload["password"] = "corta"

    response = client.post(
        "/usuarios",
        headers=auth_headers(users[1]),
        json=payload,
    )

    assert response.status_code == 422


# ============================================================
# CONSULTA
# ============================================================


def test_admin_can_list_users(client, users):
    """El administrador puede consultar el listado."""

    response = client.get(
        "/usuarios",
        headers=auth_headers(users[1]),
    )

    assert response.status_code == 200

    body = response.json()

    assert body["total"] == 3
    assert len(body["items"]) == 3
    assert body["page"] == 1
    assert body["page_size"] == 20


def test_admin_can_get_user_by_id(client, users):
    """El administrador puede consultar un usuario."""

    target = users[2]

    response = client.get(
        f"/usuarios/{target.id}",
        headers=auth_headers(users[1]),
    )

    assert response.status_code == 200
    assert response.json()["id"] == target.id


def test_unknown_user_returns_404(client, users):
    """Un identificador inexistente devuelve 404."""

    response = client.get(
        "/usuarios/999999",
        headers=auth_headers(users[1]),
    )

    assert response.status_code == 404


def test_list_users_filters_by_role(client, users):
    """El listado admite filtros por rol."""

    response = client.get(
        "/usuarios",
        headers=auth_headers(users[1]),
        params={"rol_id": 2},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["total"] == 1
    assert body["items"][0]["rol_id"] == 2


def test_list_users_searches_by_email(client, users):
    """La búsqueda localiza usuarios por correo."""

    response = client.get(
        "/usuarios",
        headers=auth_headers(users[1]),
        params={"busqueda": "rol3@example.com"},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["total"] == 1
    assert body["items"][0]["rol_id"] == 3


def test_list_users_supports_pagination(client, users):
    """El listado respeta los parámetros de paginación."""

    response = client.get(
        "/usuarios",
        headers=auth_headers(users[1]),
        params={
            "page": 2,
            "page_size": 2,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["total"] == 3
    assert body["page"] == 2
    assert body["page_size"] == 2
    assert len(body["items"]) == 1


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page_size": 0},
        {"page_size": 101},
        {"rol_id": -1},
    ],
)
def test_list_users_rejects_invalid_pagination(
    client,
    users,
    params,
):
    """Los parámetros fuera de rango devuelven 422."""

    response = client.get(
        "/usuarios",
        headers=auth_headers(users[1]),
        params=params,
    )

    assert response.status_code == 422


# ============================================================
# ACTUALIZACIÓN
# ============================================================


def test_admin_can_update_user(client, users):
    """Un administrador puede actualizar un usuario."""

    target = users[3]

    response = client.patch(
        f"/usuarios/{target.id}",
        headers=auth_headers(users[1]),
        json={
            "nombre": "Nombre Actualizado",
            "telefono": "9999999999",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["nombre"] == "Nombre Actualizado"
    assert body["telefono"] == "9999999999"


def test_admin_can_change_user_password(
    client,
    db,
    users,
):
    """Actualizar la contraseña genera un nuevo hash."""

    target = users[3]
    old_hash = target.password_hash

    response = client.patch(
        f"/usuarios/{target.id}",
        headers=auth_headers(users[1]),
        json={
            "password": NEW_PASSWORD,
        },
    )

    assert response.status_code == 200

    db.refresh(target)

    assert target.password_hash != old_hash
    assert verify_password(
        NEW_PASSWORD,
        target.password_hash,
    )


def test_update_required_field_to_null_returns_422(
    client,
    users,
):
    """Los campos obligatorios no admiten valores nulos."""

    target = users[3]

    response = client.patch(
        f"/usuarios/{target.id}",
        headers=auth_headers(users[1]),
        json={
            "nombre": None,
        },
    )

    assert response.status_code == 422


def test_update_unknown_user_returns_404(client, users):
    """No se puede modificar un usuario inexistente."""

    response = client.patch(
        "/usuarios/999999",
        headers=auth_headers(users[1]),
        json={"nombre": "Nuevo"},
    )

    assert response.status_code == 404


# ============================================================
# DESACTIVACIÓN Y REACTIVACIÓN
# ============================================================


def test_admin_can_deactivate_user(client, db, users):
    """La desactivación conserva el registro."""

    target = users[3]

    response = client.delete(
        f"/usuarios/{target.id}",
        headers=auth_headers(users[1]),
    )

    assert response.status_code == 200
    assert response.json()["activo"] is False

    db.refresh(target)

    assert target.activo is False
    assert db.get(User, target.id) is not None


def test_admin_can_reactivate_user(client, db, users):
    """Un administrador puede reactivar una cuenta."""

    target = users[3]
    target.activo = False
    db.commit()

    response = client.patch(
        f"/usuarios/{target.id}/reactivar",
        headers=auth_headers(users[1]),
    )

    assert response.status_code == 200
    assert response.json()["activo"] is True

    db.refresh(target)

    assert target.activo is True


def test_reactivate_with_inactive_role_returns_422(
    client,
    db,
    users,
):
    """No se reactiva una cuenta cuyo rol está inactivo."""

    target = users[3]
    target.activo = False
    db.commit()

    db.execute(
        text("UPDATE roles SET activo = 0 WHERE id = 3")
    )
    db.commit()

    response = client.patch(
        f"/usuarios/{target.id}/reactivar",
        headers=auth_headers(users[1]),
    )

    assert response.status_code == 422


def test_deactivate_unknown_user_returns_404(client, users):
    """La desactivación de un usuario inexistente devuelve 404."""

    response = client.delete(
        "/usuarios/999999",
        headers=auth_headers(users[1]),
    )

    assert response.status_code == 404


def test_reactivate_unknown_user_returns_404(client, users):
    """La reactivación de un usuario inexistente devuelve 404."""

    response = client.patch(
        "/usuarios/999999/reactivar",
        headers=auth_headers(users[1]),
    )

    assert response.status_code == 404


# ============================================================
# SEGURIDAD Y DOCUMENTACIÓN
# ============================================================


def test_list_response_does_not_expose_passwords(
    client,
    users,
):
    """El listado no devuelve información de contraseñas."""

    response = client.get(
        "/usuarios",
        headers=auth_headers(users[1]),
    )

    assert response.status_code == 200

    for item in response.json()["items"]:
        assert "password" not in item
        assert "password_hash" not in item


def test_users_endpoints_are_registered_in_openapi(client):
    """Swagger documenta las seis operaciones."""

    response = client.get("/openapi.json")

    assert response.status_code == 200

    paths = response.json()["paths"]

    expected = {
        "/usuarios": {"get", "post"},
        "/usuarios/{user_id}": {
            "get",
            "patch",
            "delete",
        },
        "/usuarios/{user_id}/reactivar": {"patch"},
    }

    for path, methods in expected.items():
        assert path in paths
        assert methods.issubset(paths[path].keys())

# ============================================================
# SEGURIDAD HTTP: PROTECCIONES ADMINISTRATIVAS
# ============================================================


def test_admin_cannot_deactivate_own_account_http(
    client,
    db,
    users,
):
    """Un administrador no puede desactivar su propia cuenta."""

    admin = users[1]

    response = client.delete(
        f"/usuarios/{admin.id}",
        headers=auth_headers(admin),
    )

    assert response.status_code == 403

    db.refresh(admin)
    assert admin.activo is True


def test_admin_cannot_change_own_role_http(
    client,
    db,
    users,
):
    """Un administrador no puede cambiar su propio rol."""

    admin = users[1]

    response = client.patch(
        f"/usuarios/{admin.id}",
        headers=auth_headers(admin),
        json={"rol_id": 2},
    )

    assert response.status_code == 403

    db.refresh(admin)
    assert admin.rol_id == 1


def test_admin_can_update_own_profile_http(
    client,
    db,
    users,
):
    """Un administrador puede actualizar sus datos personales."""

    admin = users[1]

    response = client.patch(
        f"/usuarios/{admin.id}",
        headers=auth_headers(admin),
        json={
            "nombre": "Administrador Actualizado",
            "telefono": "9998887777",
        },
    )

    assert response.status_code == 200
    assert response.json()["nombre"] == "Administrador Actualizado"
    assert response.json()["telefono"] == "9998887777"

    db.refresh(admin)
    assert admin.rol_id == 1
    assert admin.activo is True


def test_admin_can_deactivate_another_admin_http(
    client,
    db,
    users,
):
    """Un administrador puede desactivar a otro si permanece activo."""

    admin = users[1]

    second_admin = User(
        rol_id=1,
        nombre="Segundo",
        apellido="Administrador",
        email="segundo.admin@example.com",
        password_hash=hash_password(PASSWORD),
        activo=True,
    )

    db.add(second_admin)
    db.commit()
    db.refresh(second_admin)

    response = client.delete(
        f"/usuarios/{second_admin.id}",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200
    assert response.json()["activo"] is False

    db.refresh(second_admin)
    db.refresh(admin)

    assert second_admin.activo is False
    assert admin.activo is True


def test_admin_can_change_another_admin_role_http(
    client,
    db,
    users,
):
    """Un administrador puede cambiar el rol de otro administrador."""

    admin = users[1]

    second_admin = User(
        rol_id=1,
        nombre="Segundo",
        apellido="Administrador",
        email="segundo.admin@example.com",
        password_hash=hash_password(PASSWORD),
        activo=True,
    )

    db.add(second_admin)
    db.commit()
    db.refresh(second_admin)

    response = client.patch(
        f"/usuarios/{second_admin.id}",
        headers=auth_headers(admin),
        json={"rol_id": 2},
    )

    assert response.status_code == 200
    assert response.json()["rol_id"] == 2

    db.refresh(second_admin)
    db.refresh(admin)

    assert second_admin.rol_id == 2
    assert admin.rol_id == 1


def test_inactive_admin_cannot_update_via_http(
    client,
    db,
    users,
):
    """Un administrador inactivo no puede modificar usuarios."""

    admin = users[1]
    target = users[3]

    headers = auth_headers(admin)

    admin.activo = False
    db.commit()

    response = client.patch(
        f"/usuarios/{target.id}",
        headers=headers,
        json={"nombre": "Cambio Prohibido"},
    )

    assert response.status_code == 401

    db.refresh(target)
    assert target.nombre == "Cliente"


def test_inactive_admin_cannot_deactivate_via_http(
    client,
    db,
    users,
):
    """Un administrador inactivo no puede desactivar usuarios."""

    admin = users[1]
    target = users[3]

    headers = auth_headers(admin)

    admin.activo = False
    db.commit()

    response = client.delete(
        f"/usuarios/{target.id}",
        headers=headers,
    )

    assert response.status_code == 401

    db.refresh(target)
    assert target.activo is True


def test_inactive_admin_role_blocks_update_http(
    client,
    db,
    users,
):
    """Un rol Administrador inactivo bloquea las actualizaciones."""

    admin = users[1]
    target = users[3]

    headers = auth_headers(admin)

    db.execute(
        text("UPDATE roles SET activo = 0 WHERE id = 1")
    )
    db.commit()

    response = client.patch(
        f"/usuarios/{target.id}",
        headers=headers,
        json={"nombre": "Cambio Prohibido"},
    )

    assert response.status_code == 403

    db.refresh(target)
    assert target.nombre == "Cliente"

