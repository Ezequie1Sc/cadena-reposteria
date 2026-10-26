
"""Pruebas del servicio de autenticación mediante correo y contraseña."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from fastapi import HTTPException
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import validate_active_role
from app.core.config import settings
from app.core.jwt import decode_access_token
from app.core.login import LoginResult, authenticate_user, login_user
from app.core.security import hash_password
from app.db.session import Base
from app.modules.users.model import User
from app.shared.models.role_reference import roles_reference


PASSWORD = "PasswordSegura2026!"

INVALID_CREDENTIALS_MESSAGE = (
    "Correo electrónico o contraseña incorrectos"
)


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def db():
    """Crea una base de datos SQLite independiente para cada prueba."""

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

    # El modelo de referencia únicamente define roles.id.
    # Añadimos las columnas necesarias para las pruebas.
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
def user(db):
    """Crea un usuario activo con una contraseña Argon2id válida."""

    new_user = User(
        rol_id=1,
        nombre="Ana",
        apellido="López",
        email="ana.login@example.com",
        password_hash=hash_password(PASSWORD),
        activo=True,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


# ============================================================
# AUTENTICACIÓN EXITOSA
# ============================================================


def test_authenticate_user_with_valid_credentials(db, user):
    """Las credenciales correctas devuelven el usuario esperado."""

    authenticated = authenticate_user(
        db,
        email=user.email,
        password=PASSWORD,
    )

    assert authenticated.id == user.id
    assert authenticated.email == user.email
    assert authenticated.activo is True


def test_authenticate_user_normalizes_email(db, user):
    """El correo se normaliza antes de consultar la base de datos."""

    authenticated = authenticate_user(
        db,
        email="  ANA.LOGIN@EXAMPLE.COM  ",
        password=PASSWORD,
    )

    assert authenticated.id == user.id


# ============================================================
# CREDENCIALES INVÁLIDAS
# ============================================================


def test_nonexistent_email_returns_401(db):
    """Un correo inexistente debe devolver HTTP 401."""

    with pytest.raises(HTTPException) as exc:
        authenticate_user(
            db,
            email="inexistente@example.com",
            password=PASSWORD,
        )

    assert exc.value.status_code == 401
    assert exc.value.detail == INVALID_CREDENTIALS_MESSAGE


def test_incorrect_password_returns_401(db, user):
    """Una contraseña incorrecta debe devolver HTTP 401."""

    with pytest.raises(HTTPException) as exc:
        authenticate_user(
            db,
            email=user.email,
            password="PasswordIncorrecta2026!",
        )

    assert exc.value.status_code == 401
    assert exc.value.detail == INVALID_CREDENTIALS_MESSAGE


@pytest.mark.parametrize(
    "email,password",
    [
        ("", PASSWORD),
        ("   ", PASSWORD),
        ("ana.login@example.com", ""),
    ],
)
def test_empty_credentials_return_401(db, email, password):
    """Las credenciales vacías deben rechazarse."""

    with pytest.raises(HTTPException) as exc:
        authenticate_user(
            db,
            email=email,
            password=password,
        )

    assert exc.value.status_code == 401
    assert exc.value.detail == INVALID_CREDENTIALS_MESSAGE


def test_invalid_password_hash_returns_401(db, user):
    """Un hash almacenado inválido no permite iniciar sesión."""

    user.password_hash = "hash-invalido"
    db.commit()

    with pytest.raises(HTTPException) as exc:
        authenticate_user(
            db,
            email=user.email,
            password=PASSWORD,
        )

    assert exc.value.status_code == 401
    assert exc.value.detail == INVALID_CREDENTIALS_MESSAGE


def test_missing_user_and_wrong_password_have_same_error(db, user):
    """No distingue entre correo inexistente y contraseña incorrecta."""

    errors = []

    for email, password in [
        ("inexistente@example.com", PASSWORD),
        (user.email, "PasswordIncorrecta2026!"),
    ]:
        with pytest.raises(HTTPException) as exc:
            authenticate_user(
                db,
                email=email,
                password=password,
            )

        errors.append(
            (
                exc.value.status_code,
                exc.value.detail,
            )
        )

    assert errors[0] == errors[1]


# ============================================================
# ESTADO DEL USUARIO Y DEL ROL
# ============================================================


def test_inactive_user_returns_401(db, user):
    """Un usuario inactivo recibe el mismo error genérico."""

    user.activo = False
    db.commit()

    with pytest.raises(HTTPException) as exc:
        authenticate_user(
            db,
            email=user.email,
            password=PASSWORD,
        )

    assert exc.value.status_code == 401
    assert exc.value.detail == INVALID_CREDENTIALS_MESSAGE
    assert exc.value.headers["WWW-Authenticate"] == "Bearer"


def test_inactive_role_returns_401(db, user):
    """Un rol inactivo no revela información de la cuenta."""

    db.execute(
        text(
            "UPDATE roles "
            "SET activo = 0 "
            "WHERE id = :role_id"
        ),
        {"role_id": user.rol_id},
    )

    db.commit()

    with pytest.raises(HTTPException) as exc:
        authenticate_user(
            db,
            email=user.email,
            password=PASSWORD,
        )

    assert exc.value.status_code == 401
    assert exc.value.detail == INVALID_CREDENTIALS_MESSAGE
    assert exc.value.headers["WWW-Authenticate"] == "Bearer"


def test_nonexistent_role_returns_403(db):
    """La validación directa rechaza identificadores inexistentes."""

    with pytest.raises(HTTPException) as exc:
        validate_active_role(db, 999)

    assert exc.value.status_code == 403
    assert exc.value.detail == (
        "El usuario no tiene un rol válido"
    )


# ============================================================
# GENERACIÓN Y SEGURIDAD DEL JWT
# ============================================================


def test_login_generates_valid_access_token(db, user):
    """El inicio de sesión exitoso genera un JWT válido."""

    result = login_user(
        db,
        email=user.email,
        password=PASSWORD,
    )

    assert isinstance(result, LoginResult)
    assert result.token_type == "bearer"
    assert isinstance(result.access_token, str)

    assert decode_access_token(result.access_token) == user.id


def test_login_token_contains_expected_claims(db, user):
    """El JWT contiene las reclamaciones de autenticación esperadas."""

    result = login_user(
        db,
        email=user.email,
        password=PASSWORD,
    )

    payload = jwt.decode(
        result.access_token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )

    assert payload["sub"] == str(user.id)
    assert payload["type"] == "access"

    assert "iat" in payload
    assert "nbf" in payload
    assert "exp" in payload


def test_login_token_does_not_expose_sensitive_data(db, user):
    """El JWT no contiene contraseñas ni información sensible."""

    result = login_user(
        db,
        email=user.email,
        password=PASSWORD,
    )

    payload = jwt.decode(
        result.access_token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )

    assert "password" not in payload
    assert "password_hash" not in payload
    assert "email" not in payload

    assert PASSWORD not in result.access_token
    assert user.password_hash not in result.access_token


def test_login_rejects_invalid_password(db, user):
    """El servicio no emite tokens con credenciales incorrectas."""

    with pytest.raises(HTTPException) as exc:
        login_user(
            db,
            email=user.email,
            password="PasswordIncorrecta2026!",
        )

    assert exc.value.status_code == 401
    assert exc.value.detail == INVALID_CREDENTIALS_MESSAGE
