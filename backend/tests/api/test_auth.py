
"""Pruebas HTTP del endpoint POST /auth/login."""

import jwt
import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.auth import get_rate_limit_session_factory
from app.core.config import settings
from app.core.jwt import decode_access_token
from app.core.security import hash_password
from app.db.session import Base, get_db
from app.main import app
from app.modules.auth.rate_limit_model import AuthRateLimit
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
            AuthRateLimit.__table__,
        ],
    )

    # El modelo de referencia solo define roles.id.
    # Añadimos las columnas que utiliza la autenticación.
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

    TestSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )

    try:
        with TestSessionLocal() as session:
            yield session
    finally:
        engine.dispose()


@pytest.fixture
def user(db):
    """Registra un usuario activo con contraseña Argon2id."""

    new_user = User(
        rol_id=1,
        nombre="Ana",
        apellido="López",
        email="ana.http@example.com",
        password_hash=hash_password(PASSWORD),
        activo=True,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@pytest.fixture
def client(db):
    """Crea un cliente HTTP aislado de PostgreSQL."""

    def override_get_db():
        yield db

    test_session_factory = sessionmaker(
        bind=db.get_bind(),
        autoflush=False,
        expire_on_commit=False,
    )

    def override_rate_limit_session_factory():
        return test_session_factory

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[
        get_rate_limit_session_factory
    ] = override_rate_limit_session_factory

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(
            get_rate_limit_session_factory,
            None,
        )


# ============================================================
# UTILIDADES
# ============================================================


def login_payload(
    email: str = "ana.http@example.com",
    password: str = PASSWORD,
) -> dict[str, str]:
    """Construye las credenciales para una solicitud HTTP."""

    return {
        "email": email,
        "password": password,
    }


# ============================================================
# LOGIN EXITOSO
# ============================================================


def test_login_returns_200_with_valid_credentials(client, user):
    """Las credenciales válidas permiten iniciar sesión."""

    response = client.post(
        "/auth/login",
        json=login_payload(),
    )

    assert response.status_code == 200

    body = response.json()

    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_login_returns_valid_jwt(client, user):
    """El token devuelto puede validarse correctamente."""

    response = client.post(
        "/auth/login",
        json=login_payload(),
    )

    assert response.status_code == 200

    token = response.json()["access_token"]

    assert decode_access_token(token) == user.id


def test_login_normalizes_email(client, user):
    """El inicio de sesión acepta mayúsculas y espacios."""

    response = client.post(
        "/auth/login",
        json=login_payload(
            email="  ANA.HTTP@EXAMPLE.COM  ",
        ),
    )

    assert response.status_code == 200

    token = response.json()["access_token"]

    assert decode_access_token(token) == user.id


def test_login_response_does_not_expose_sensitive_data(client, user):
    """La respuesta no revela contraseñas ni hashes."""

    response = client.post(
        "/auth/login",
        json=login_payload(),
    )

    assert response.status_code == 200

    body = response.json()

    assert set(body) == {
        "access_token",
        "token_type",
    }

    assert "password" not in body
    assert "password_hash" not in body
    assert "email" not in body

    token = body["access_token"]

    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )

    assert "password" not in payload
    assert "password_hash" not in payload
    assert "email" not in payload

    assert PASSWORD not in token
    assert user.password_hash not in token


# ============================================================
# CREDENCIALES INCORRECTAS
# ============================================================


def test_login_wrong_password_returns_401(client, user):
    """Una contraseña incorrecta devuelve HTTP 401."""

    response = client.post(
        "/auth/login",
        json=login_payload(
            password="PasswordIncorrecta2026!",
        ),
    )

    assert response.status_code == 401

    assert response.json()["detail"] == (
        INVALID_CREDENTIALS_MESSAGE
    )

    assert response.headers["www-authenticate"] == "Bearer"


def test_login_unknown_email_returns_401(client):
    """Un correo inexistente devuelve HTTP 401."""

    response = client.post(
        "/auth/login",
        json=login_payload(
            email="inexistente@example.com",
        ),
    )

    assert response.status_code == 401

    assert response.json()["detail"] == (
        INVALID_CREDENTIALS_MESSAGE
    )


def test_login_wrong_password_and_unknown_email_have_same_error(
    client,
    user,
):
    """Los errores no distinguen la existencia de una cuenta."""

    wrong_password = client.post(
        "/auth/login",
        json=login_payload(
            password="PasswordIncorrecta2026!",
        ),
    )

    unknown_email = client.post(
        "/auth/login",
        json=login_payload(
            email="inexistente@example.com",
        ),
    )

    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401

    assert wrong_password.json() == unknown_email.json()


# ============================================================
# CUENTAS Y ROLES INACTIVOS
# ============================================================


def test_login_inactive_user_returns_401(client, db, user):
    """Una cuenta desactivada no puede iniciar sesión."""

    user.activo = False
    db.commit()

    response = client.post(
        "/auth/login",
        json=login_payload(),
    )

    assert response.status_code == 401

    assert response.json()["detail"] == (
        INVALID_CREDENTIALS_MESSAGE
    )


def test_login_inactive_role_returns_401(client, db, user):
    """Un rol inactivo impide iniciar sesión."""

    db.execute(
        text(
            "UPDATE roles "
            "SET activo = 0 "
            "WHERE id = :role_id"
        ),
        {"role_id": user.rol_id},
    )

    db.commit()

    response = client.post(
        "/auth/login",
        json=login_payload(),
    )

    assert response.status_code == 401

    assert response.json()["detail"] == (
        INVALID_CREDENTIALS_MESSAGE
    )


# ============================================================
# VALIDACIÓN DE ENTRADA
# ============================================================


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"email": "ana.http@example.com"},
        {"password": PASSWORD},
        {"email": "", "password": PASSWORD},
        {"email": "ana.http@example.com", "password": ""},
        {"email": 123, "password": PASSWORD},
        {"email": "ana.http@example.com", "password": 123},
        {
            "email": "ana.http@example.com",
            "password": PASSWORD,
            "campo_extra": "no permitido",
        },
    ],
)
def test_login_invalid_payload_returns_422(client, payload):
    """Pydantic rechaza solicitudes incompletas o inválidas."""

    response = client.post(
        "/auth/login",
        json=payload,
    )

    assert response.status_code == 422


def test_login_rejects_password_in_query_string(client, user):
    """El endpoint no acepta credenciales solo por query params."""

    response = client.post(
        "/auth/login",
        params=login_payload(),
    )

    assert response.status_code == 422


def test_login_response_has_json_content_type(client, user):
    """El endpoint devuelve una respuesta JSON."""

    response = client.post(
        "/auth/login",
        json=login_payload(),
    )

    assert response.status_code == 200

    assert response.headers["content-type"].startswith(
        "application/json"
    )


# ============================================================
# DOCUMENTACIÓN OPENAPI
# ============================================================


def test_login_endpoint_is_registered_in_openapi(client):
    """El endpoint está registrado en la aplicación real."""

    response = client.get("/openapi.json")

    assert response.status_code == 200

    paths = response.json()["paths"]

    assert "/auth/login" in paths
    assert "post" in paths["/auth/login"]


def test_login_endpoint_has_authentication_tag(client):
    """Swagger agrupa el endpoint bajo Autenticación."""

    response = client.get("/openapi.json")

    assert response.status_code == 200

    operation = response.json()["paths"]["/auth/login"]["post"]

    assert "Autenticación" in operation["tags"]


# ============================================================
# RATE LIMITING
# ============================================================


def test_login_allows_five_requests_for_same_email(client, user):
    """Permite cinco solicitudes dentro de la ventana."""

    for _ in range(5):
        response = client.post(
            "/auth/login",
            json=login_payload(
                password="PasswordIncorrecta2026!",
            ),
        )

        assert response.status_code == 401


def test_login_sixth_request_returns_429(client, user):
    """La sexta solicitud de la misma IP y correo se bloquea."""

    for _ in range(5):
        response = client.post(
            "/auth/login",
            json=login_payload(
                password="PasswordIncorrecta2026!",
            ),
        )

        assert response.status_code == 401

    blocked_response = client.post(
        "/auth/login",
        json=login_payload(
            password="PasswordIncorrecta2026!",
        ),
    )

    assert blocked_response.status_code == 429


def test_login_rate_limit_returns_retry_after(client, user):
    """La respuesta HTTP 429 indica cuánto tiempo esperar."""

    for _ in range(6):
        response = client.post(
            "/auth/login",
            json=login_payload(
                password="PasswordIncorrecta2026!",
            ),
        )

    assert response.status_code == 429

    assert "retry-after" in response.headers

    retry_after = int(response.headers["retry-after"])

    assert retry_after > 0
    assert retry_after <= 61


def test_login_rate_limit_normalizes_email(client, user):
    """Las variaciones de mayúsculas y espacios comparten el límite."""

    emails = [
        "ana.http@example.com",
        "ANA.HTTP@EXAMPLE.COM",
        "  ana.http@example.com  ",
        "Ana.Http@Example.Com",
        "ana.http@example.com",
    ]

    for email in emails:
        response = client.post(
            "/auth/login",
            json=login_payload(
                email=email,
                password="PasswordIncorrecta2026!",
            ),
        )

        assert response.status_code == 401

    blocked_response = client.post(
        "/auth/login",
        json=login_payload(
            email="ANA.HTTP@EXAMPLE.COM",
            password="PasswordIncorrecta2026!",
        ),
    )

    assert blocked_response.status_code == 429


def test_login_rate_limit_does_not_expose_identifiers(client, user):
    """La respuesta de bloqueo no revela IP, correo ni claves."""

    for _ in range(6):
        response = client.post(
            "/auth/login",
            json=login_payload(
                password="PasswordIncorrecta2026!",
            ),
        )

    assert response.status_code == 429

    body = response.json()

    assert "ana.http@example.com" not in str(body)
    assert "password" not in str(body).lower()
    assert "key" not in body
