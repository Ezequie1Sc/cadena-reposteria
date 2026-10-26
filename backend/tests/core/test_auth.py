
"""Pruebas HTTP de autenticación y validación de usuarios activos."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import CurrentUser, validate_active_role
from app.core.config import settings
from app.core.jwt import create_access_token
from app.db.session import Base, get_db
from app.modules.users.model import User
from app.shared.models.role_reference import roles_reference


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def db():
    """Crea una base SQLite independiente para cada prueba."""

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

    # El modelo de referencia solo define roles.id.
    # La tabla real también contiene la columna activo.
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "ALTER TABLE roles "
            "ADD COLUMN activo BOOLEAN NOT NULL DEFAULT 1"
        )

        connection.exec_driver_sql(
            "INSERT INTO roles (id, activo) "
            "VALUES (1, 1), (2, 0)"
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
def user(db):
    """Registra un usuario activo asociado a un rol activo."""

    new_user = User(
        rol_id=1,
        nombre="Ana",
        apellido="López",
        email="ana.auth@example.com",
        password_hash="hash-de-prueba-no-utilizable",
        activo=True,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@pytest.fixture
def client(db):
    """Crea una API de prueba con un endpoint protegido."""

    app = FastAPI()

    @app.get("/protegido")
    def protected_route(current_user: CurrentUser):
        return {
            "id": current_user.id,
            "email": current_user.email,
            "rol_id": current_user.rol_id,
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


def authorization_header(user_id: int) -> dict[str, str]:
    """Construye un encabezado Authorization válido."""

    token = create_access_token(user_id)

    return {
        "Authorization": f"Bearer {token}",
    }


# ============================================================
# AUTENTICACIÓN EXITOSA
# ============================================================


def test_authenticated_user_can_access(client, user):
    """Un usuario activo con un rol activo puede autenticarse."""

    response = client.get(
        "/protegido",
        headers=authorization_header(user.id),
    )

    assert response.status_code == 200

    assert response.json() == {
        "id": user.id,
        "email": user.email,
        "rol_id": 1,
    }


# ============================================================
# TOKENS INVÁLIDOS
# ============================================================


def test_missing_token_returns_401(client):
    """Una solicitud sin token debe ser rechazada."""

    response = client.get("/protegido")

    assert response.status_code == 401

    assert response.headers["www-authenticate"] == "Bearer"


def test_invalid_token_returns_401(client):
    """Un JWT inválido no permite acceder."""

    response = client.get(
        "/protegido",
        headers={
            "Authorization": "Bearer token.invalido",
        },
    )

    assert response.status_code == 401


def test_expired_token_returns_401(client, user):
    """Un token expirado debe devolver HTTP 401."""

    now = datetime.now(timezone.utc)

    token = jwt.encode(
        {
            "sub": str(user.id),
            "iat": now - timedelta(minutes=10),
            "nbf": now - timedelta(minutes=10),
            "exp": now - timedelta(minutes=5),
            "type": "access",
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    response = client.get(
        "/protegido",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 401


# ============================================================
# VALIDACIÓN DE USUARIOS
# ============================================================


def test_nonexistent_user_returns_401(client):
    """Un token de un usuario inexistente debe rechazarse."""

    response = client.get(
        "/protegido",
        headers=authorization_header(999),
    )

    assert response.status_code == 401


def test_inactive_user_returns_401(client, db, user):
    """Un usuario desactivado no puede autenticarse."""

    user.activo = False
    db.commit()

    response = client.get(
        "/protegido",
        headers=authorization_header(user.id),
    )

    assert response.status_code == 401


# ============================================================
# VALIDACIÓN DE ROLES
# ============================================================


def test_inactive_role_returns_403(client, db, user):
    """Un usuario con un rol inactivo no puede acceder."""

    user.rol_id = 2
    db.commit()

    response = client.get(
        "/protegido",
        headers=authorization_header(user.id),
    )

    assert response.status_code == 403

    assert response.json()["detail"] == (
        "El rol del usuario está inactivo"
    )


def test_nonexistent_role_returns_403(db):
    """Un identificador de rol inexistente debe devolver 403."""

    with pytest.raises(HTTPException) as exc:
        validate_active_role(db, 999)

    assert exc.value.status_code == 403

    assert exc.value.detail == (
        "El usuario no tiene un rol válido"
    )


# ============================================================
# REVOCACIÓN DE ACCESO
# ============================================================


def test_deactivated_user_loses_access_with_existing_token(
    client,
    db,
    user,
):
    """Desactivar una cuenta invalida su acceso inmediatamente."""

    headers = authorization_header(user.id)

    first_response = client.get(
        "/protegido",
        headers=headers,
    )

    assert first_response.status_code == 200

    user.activo = False
    db.commit()

    second_response = client.get(
        "/protegido",
        headers=headers,
    )

    assert second_response.status_code == 401


def test_deactivated_role_revokes_existing_token(
    client,
    db,
    user,
):
    """Desactivar un rol revoca el acceso con el mismo JWT."""

    headers = authorization_header(user.id)

    first_response = client.get(
        "/protegido",
        headers=headers,
    )

    assert first_response.status_code == 200

    db.execute(
        text(
            "UPDATE roles "
            "SET activo = 0 "
            "WHERE id = :role_id"
        ),
        {"role_id": user.rol_id},
    )

    db.commit()

    second_response = client.get(
        "/protegido",
        headers=headers,
    )

    assert second_response.status_code == 403

    assert second_response.json()["detail"] == (
        "El rol del usuario está inactivo"
    )
