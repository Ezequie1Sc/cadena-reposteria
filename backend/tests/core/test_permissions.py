
"""Pruebas HTTP de autorización basada en roles (RBAC)."""

from datetime import timedelta

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.jwt import create_access_token
from app.core.permissions import AdminUser, RoleID, StaffUser, require_roles
from app.db.session import Base, get_db
from app.modules.users.model import User
from app.shared.models.role_reference import roles_reference


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def db():
    """Crea una base SQLite aislada para cada prueba."""

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
        tables=[
            roles_reference,
            User.__table__,
        ],
    )

    # El modelo de referencia solo declara roles.id.
    # La tabla real también contiene nombre y activo.
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "ALTER TABLE roles "
            "ADD COLUMN nombre VARCHAR(50)"
        )

        connection.exec_driver_sql(
            "ALTER TABLE roles "
            "ADD COLUMN activo BOOLEAN NOT NULL DEFAULT 1"
        )

        connection.execute(
            text(
                "INSERT INTO roles (id, nombre, activo) VALUES "
                "(1, 'Administrador', 1), "
                "(2, 'Empleado', 1), "
                "(3, 'Cliente', 1)"
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
    """Crea un usuario por cada rol del sistema."""

    records = {
        "admin": User(
            rol_id=RoleID.ADMINISTRADOR,
            nombre="Ana",
            apellido="Admin",
            email="admin@example.com",
            password_hash="hash-de-prueba",
            activo=True,
        ),
        "employee": User(
            rol_id=RoleID.EMPLEADO,
            nombre="Luis",
            apellido="Empleado",
            email="empleado@example.com",
            password_hash="hash-de-prueba",
            activo=True,
        ),
        "customer": User(
            rol_id=RoleID.CLIENTE,
            nombre="María",
            apellido="Cliente",
            email="cliente@example.com",
            password_hash="hash-de-prueba",
            activo=True,
        ),
    }

    db.add_all(records.values())
    db.commit()

    for user in records.values():
        db.refresh(user)

    return records


@pytest.fixture
def client(db):
    """Expone endpoints con autorización administrativa y de personal."""

    app = FastAPI()

    @app.get("/administracion")
    def admin_route(current_user: AdminUser):
        return {
            "message": "Acceso administrativo autorizado",
            "user_id": current_user.id,
        }

    @app.get("/personal")
    def staff_route(current_user: StaffUser):
        return {
            "message": "Acceso de personal autorizado",
            "user_id": current_user.id,
        }

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# ============================================================
# UTILIDADES
# ============================================================


def auth_headers(user_id: int) -> dict[str, str]:
    """Construye un encabezado Bearer válido."""

    return {
        "Authorization": f"Bearer {create_access_token(user_id)}",
    }


# ============================================================
# ACCESO ADMINISTRATIVO
# ============================================================


def test_admin_can_access_admin_route(client, users):
    """Un administrador puede acceder a operaciones administrativas."""

    response = client.get(
        "/administracion",
        headers=auth_headers(users["admin"].id),
    )

    assert response.status_code == 200
    assert response.json()["user_id"] == users["admin"].id


def test_employee_cannot_access_admin_route(client, users):
    """Un empleado no puede administrar usuarios."""

    response = client.get(
        "/administracion",
        headers=auth_headers(users["employee"].id),
    )

    assert response.status_code == 403


def test_customer_cannot_access_admin_route(client, users):
    """Un cliente no puede acceder a operaciones administrativas."""

    response = client.get(
        "/administracion",
        headers=auth_headers(users["customer"].id),
    )

    assert response.status_code == 403


# ============================================================
# ACCESO DE PERSONAL
# ============================================================


def test_admin_can_access_staff_route(client, users):
    """Un administrador también puede acceder a operaciones del personal."""

    response = client.get(
        "/personal",
        headers=auth_headers(users["admin"].id),
    )

    assert response.status_code == 200


def test_employee_can_access_staff_route(client, users):
    """Un empleado puede acceder a operaciones del personal."""

    response = client.get(
        "/personal",
        headers=auth_headers(users["employee"].id),
    )

    assert response.status_code == 200


def test_customer_cannot_access_staff_route(client, users):
    """Un cliente no puede acceder a operaciones del personal."""

    response = client.get(
        "/personal",
        headers=auth_headers(users["customer"].id),
    )

    assert response.status_code == 403


# ============================================================
# AUTENTICACIÓN OBLIGATORIA
# ============================================================


@pytest.mark.parametrize(
    "path",
    ["/administracion", "/personal"],
)
def test_missing_token_returns_401(client, path):
    """Las rutas protegidas rechazan solicitudes sin JWT."""

    response = client.get(path)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "path",
    ["/administracion", "/personal"],
)
def test_invalid_token_returns_401(client, path):
    """Las rutas protegidas rechazan tokens inválidos."""

    response = client.get(
        path,
        headers={"Authorization": "Bearer token.invalido"},
    )

    assert response.status_code == 401


def test_expired_token_returns_401(client, users):
    """Un token expirado no concede permisos administrativos."""

    # Se crea un token válido y se comprueba su estructura.
    # La expiración se prueba mediante un JWT firmado
    # cuyo vencimiento ya ocurrió.
    from datetime import datetime, timezone

    import jwt

    from app.core.config import settings

    now = datetime.now(timezone.utc)

    token = jwt.encode(
        {
            "sub": str(users["admin"].id),
            "iat": now - timedelta(minutes=10),
            "nbf": now - timedelta(minutes=10),
            "exp": now - timedelta(minutes=5),
            "type": "access",
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    response = client.get(
        "/administracion",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


# ============================================================
# REVOCACIÓN DE PERMISOS
# ============================================================


def test_inactive_user_cannot_access_admin_route(
    client,
    db,
    users,
):
    """Desactivar una cuenta revoca su acceso administrativo."""

    admin = users["admin"]
    headers = auth_headers(admin.id)

    assert client.get(
        "/administracion",
        headers=headers,
    ).status_code == 200

    admin.activo = False
    db.commit()

    response = client.get(
        "/administracion",
        headers=headers,
    )

    assert response.status_code == 401


def test_inactive_role_cannot_access_staff_route(
    client,
    db,
    users,
):
    """Desactivar un rol revoca sus permisos."""

    employee = users["employee"]
    headers = auth_headers(employee.id)

    assert client.get(
        "/personal",
        headers=headers,
    ).status_code == 200

    db.execute(
        text(
            "UPDATE roles "
            "SET activo = 0 "
            "WHERE id = :role_id"
        ),
        {"role_id": RoleID.EMPLEADO},
    )
    db.commit()

    response = client.get(
        "/personal",
        headers=headers,
    )

    assert response.status_code == 403


def test_role_change_revokes_admin_permissions(
    client,
    db,
    users,
):
    """Cambiar un administrador a empleado revoca sus permisos."""

    admin = users["admin"]
    headers = auth_headers(admin.id)

    assert client.get(
        "/administracion",
        headers=headers,
    ).status_code == 200

    admin.rol_id = RoleID.EMPLEADO
    db.commit()

    response = client.get(
        "/administracion",
        headers=headers,
    )

    assert response.status_code == 403


# ============================================================
# VALIDACIÓN DE LA CONFIGURACIÓN RBAC
# ============================================================


def test_role_identifiers_match_database():
    """Comprueba los identificadores de los roles establecidos."""

    assert RoleID.ADMINISTRADOR == 1
    assert RoleID.EMPLEADO == 2
    assert RoleID.CLIENTE == 3


def test_require_roles_rejects_empty_configuration():
    """No se permite crear una dependencia sin roles autorizados."""

    with pytest.raises(ValueError):
        require_roles()
