
"""Pruebas HTTP del registro público de clientes."""

import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import verify_password
from app.db.session import Base, get_db
from app.main import app
from app.modules.users.model import User
from app.shared.models.role_reference import roles_reference


PASSWORD = "PasswordSegura2026!"
REGISTER_URL = "/auth/register"


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

    with engine.begin() as connection:
        connection.exec_driver_sql(
            "ALTER TABLE roles ADD COLUMN nombre VARCHAR(50)"
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

    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )

    try:
        with session_factory() as session:
            yield session
    finally:
        engine.dispose()


@pytest.fixture
def client(db):
    """Crea un cliente HTTP sin utilizar Supabase."""

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


def registration_payload(**changes):
    """Construye una solicitud válida y permite modificar campos."""

    payload = {
        "nombre": "Ana",
        "apellido": "López",
        "email": "ana.registro@example.com",
        "password": PASSWORD,
        "telefono": "9991234567",
    }

    payload.update(changes)
    return payload


def test_register_returns_201(client):
    """El registro exitoso devuelve HTTP 201."""

    response = client.post(
        REGISTER_URL,
        json=registration_payload(),
    )

    assert response.status_code == 201


def test_register_creates_customer_role(client, db):
    """El registro asigna exclusivamente el rol Cliente."""

    response = client.post(
        REGISTER_URL,
        json=registration_payload(),
    )

    assert response.status_code == 201

    user = db.scalar(
        select(User).where(
            User.email == "ana.registro@example.com"
        )
    )

    assert user is not None
    assert user.rol_id == 3
    assert user.activo is True


def test_register_hashes_password(client, db):
    """La contraseña se almacena mediante Argon2id."""

    response = client.post(
        REGISTER_URL,
        json=registration_payload(),
    )

    assert response.status_code == 201

    user = db.scalar(select(User))

    assert user is not None
    assert user.password_hash != PASSWORD
    assert user.password_hash.startswith("$argon2id$")
    assert verify_password(PASSWORD, user.password_hash)


def test_register_does_not_expose_password(client):
    """La respuesta nunca incluye información sensible."""

    response = client.post(
        REGISTER_URL,
        json=registration_payload(),
    )

    assert response.status_code == 201

    body = response.json()

    assert set(body) == {
        "id",
        "nombre",
        "apellido",
        "email",
        "telefono",
        "activo",
    }

    assert "password" not in body
    assert "password_hash" not in body
    assert PASSWORD not in str(body)


def test_register_normalizes_email(client, db):
    """El correo se almacena en minúsculas."""

    response = client.post(
        REGISTER_URL,
        json=registration_payload(
            email="ANA.REGISTRO@EXAMPLE.COM"
        ),
    )

    assert response.status_code == 201

    user = db.scalar(select(User))

    assert user.email == "ana.registro@example.com"


def test_register_duplicate_email_returns_409(client, db):
    """No permite registrar dos cuentas con el mismo correo."""

    first_response = client.post(
        REGISTER_URL,
        json=registration_payload(),
    )

    second_response = client.post(
        REGISTER_URL,
        json=registration_payload(),
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409

    users = db.scalars(select(User)).all()
    assert len(users) == 1


def test_register_duplicate_email_is_case_insensitive(client):
    """Los correos duplicados se detectan sin distinguir mayúsculas."""

    first_response = client.post(
        REGISTER_URL,
        json=registration_payload(),
    )

    second_response = client.post(
        REGISTER_URL,
        json=registration_payload(
            email="ANA.REGISTRO@EXAMPLE.COM"
        ),
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409


@pytest.mark.parametrize(
    "changes",
    [
        {"nombre": ""},
        {"nombre": "   "},
        {"apellido": ""},
        {"apellido": "   "},
        {"email": "correo-invalido"},
        {"email": ""},
        {"password": "123"},
        {"password": "SoloLetrasSinNumeros"},
        {"password": "123456789012"},
        {"telefono": "123"},
    ],
)
def test_register_invalid_data_returns_422(client, changes):
    """Rechaza datos que incumplen las reglas de validación."""

    response = client.post(
        REGISTER_URL,
        json=registration_payload(**changes),
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "field",
    [
        "nombre",
        "apellido",
        "email",
        "password",
    ],
)
def test_register_missing_required_field_returns_422(
    client,
    field,
):
    """Los campos obligatorios deben estar presentes."""

    payload = registration_payload()
    payload.pop(field)

    response = client.post(
        REGISTER_URL,
        json=payload,
    )

    assert response.status_code == 422


def test_register_rejects_role_assignment(client, db):
    """Un solicitante no puede asignarse el rol Administrador."""

    response = client.post(
        REGISTER_URL,
        json=registration_payload(rol_id=1),
    )

    assert response.status_code == 422
    assert db.scalar(select(User)) is None


def test_register_rejects_admin_flags(client, db):
    """El registro no permite introducir campos privilegiados."""

    response = client.post(
        REGISTER_URL,
        json=registration_payload(
            activo=True,
            password_hash="hash-falso",
        ),
    )

    assert response.status_code == 422
    assert db.scalar(select(User)) is None


def test_register_inactive_customer_role_returns_503(
    client,
    db,
):
    """No registra clientes cuando el rol está desactivado."""

    db.execute(
        text(
            "UPDATE roles SET activo = 0 WHERE id = 3"
        )
    )
    db.commit()

    response = client.post(
        REGISTER_URL,
        json=registration_payload(),
    )

    assert response.status_code == 503
    assert db.scalar(select(User)) is None


def test_register_missing_customer_role_returns_503(
    client,
    db,
):
    """No registra clientes si el rol Cliente no existe."""

    db.execute(
        text("DELETE FROM roles WHERE id = 3")
    )
    db.commit()

    response = client.post(
        REGISTER_URL,
        json=registration_payload(),
    )

    assert response.status_code == 503
    assert db.scalar(select(User)) is None


def test_register_without_phone_returns_201(client, db):
    """El teléfono es opcional."""

    payload = registration_payload()
    payload.pop("telefono")

    response = client.post(
        REGISTER_URL,
        json=payload,
    )

    assert response.status_code == 201
    assert response.json()["telefono"] is None


def test_register_is_documented_in_openapi(client):
    """El registro aparece en la documentación de FastAPI."""

    response = client.get("/openapi.json")

    assert response.status_code == 200

    paths = response.json()["paths"]

    assert REGISTER_URL in paths
    assert "post" in paths[REGISTER_URL]

    operation = paths[REGISTER_URL]["post"]

    assert operation["responses"]["201"]
    assert "Autenticación" in operation["tags"]
