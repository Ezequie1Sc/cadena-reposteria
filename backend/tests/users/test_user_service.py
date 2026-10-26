
"""Pruebas de la lógica de negocio del módulo de usuarios."""

import pytest

from fastapi import HTTPException
from sqlalchemy import Boolean, Column, MetaData, Table, create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import verify_password
from app.db.session import Base
from app.modules.users.model import User
from app.modules.users.schemas import UserCreate, UserUpdate
from app.modules.users.service import UserService
from app.shared.models.role_reference import roles_reference


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

    # La referencia de roles solo declara el identificador.
    # Añadimos la columna real necesaria para probar el servicio.
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "ALTER TABLE roles ADD COLUMN activo BOOLEAN NOT NULL DEFAULT 1"
        )
        connection.exec_driver_sql(
            "INSERT INTO roles (id, activo) VALUES (1, 1), (2, 0)"
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
def service():
    return UserService()


@pytest.fixture
def user_data():
    return UserCreate(
        rol_id=1,
        nombre="Ana",
        apellido="López",
        email="ana@example.com",
        password="PasswordSegura2026!",
        telefono="9991234567",
    )


@pytest.fixture
def created_user(db, service, user_data):
    return service.create_user(db, user_data)


def test_create_user_hashes_password(db, service, user_data):
    result = service.create_user(db, user_data)

    user = db.get(User, result.id)

    assert result.email == "ana@example.com"
    assert user is not None
    assert user.password_hash != user_data.password
    assert user.password_hash.startswith("$argon2id$")
    assert verify_password(user_data.password, user.password_hash)


def test_user_response_does_not_expose_password(
    db, service, created_user
):
    response = service.get_user_by_id(db, created_user.id)

    assert "password_hash" not in response.model_dump()
    assert "password" not in response.model_dump()


def test_create_user_rejects_duplicate_email(
    db, service, user_data, created_user
):
    with pytest.raises(HTTPException) as exc:
        service.create_user(db, user_data)

    assert exc.value.status_code == 409


def test_create_user_rejects_inactive_role(db, service):
    data = UserCreate(
        rol_id=2,
        nombre="Carlos",
        apellido="Pérez",
        email="carlos@example.com",
        password="PasswordSegura2026!",
    )

    with pytest.raises(HTTPException) as exc:
        service.create_user(db, data)

    assert exc.value.status_code == 422


def test_create_user_rejects_missing_role(db, service):
    data = UserCreate(
        rol_id=999,
        nombre="Carlos",
        apellido="Pérez",
        email="carlos@example.com",
        password="PasswordSegura2026!",
    )

    with pytest.raises(HTTPException) as exc:
        service.create_user(db, data)

    assert exc.value.status_code == 422


def test_get_user_by_id(db, service, created_user):
    result = service.get_user_by_id(db, created_user.id)

    assert result.id == created_user.id
    assert result.nombre == "Ana"


def test_get_user_by_id_returns_404(db, service):
    with pytest.raises(HTTPException) as exc:
        service.get_user_by_id(db, 999)

    assert exc.value.status_code == 404


def test_update_user(db, service, created_user):
    result = service.update_user(
        db,
        created_user.id,
        UserUpdate(nombre="María"),
    )

    assert result.nombre == "María"
    assert result.email == "ana@example.com"


def test_update_password(db, service, created_user):
    new_password = "NuevaPasswordSegura2026!"

    service.update_user(
        db,
        created_user.id,
        UserUpdate(password=new_password),
    )

    user = db.get(User, created_user.id)

    assert verify_password(new_password, user.password_hash)
    assert not verify_password(
        "PasswordSegura2026!",
        user.password_hash,
    )


def test_update_rejects_null_required_field(
    db, service, created_user
):
    with pytest.raises(HTTPException) as exc:
        service.update_user(
            db,
            created_user.id,
            UserUpdate(nombre=None),
        )

    assert exc.value.status_code == 422


def test_deactivate_user(db, service, created_user):
    result = service.deactivate_user(db, created_user.id)

    assert result.activo is False


def test_reactivate_user(db, service, created_user):
    service.deactivate_user(db, created_user.id)

    result = service.reactivate_user(db, created_user.id)

    assert result.activo is True


def test_get_users_filters_by_search(db, service, created_user):
    result = service.get_users(
        db,
        busqueda="ana@example.com",
    )

    assert result["total"] == 1
    assert len(result["items"]) == 1
    assert result["items"][0].id == created_user.id


def test_get_users_search_without_matches(
    db, service, created_user
):
    result = service.get_users(
        db,
        busqueda="noexiste@example.com",
    )

    assert result["total"] == 0
    assert result["items"] == []


def test_get_users_pagination(db, service, created_user):
    result = service.get_users(
        db,
        page=1,
        page_size=1,
    )

    assert result["total"] == 1
    assert len(result["items"]) == 1
    assert result["page"] == 1
    assert result["page_size"] == 1


def test_get_users_rejects_invalid_page(db, service):
    with pytest.raises(HTTPException) as exc:
        service.get_users(db, page=0)

    assert exc.value.status_code == 422


def test_get_users_rejects_invalid_page_size(db, service):
    with pytest.raises(HTTPException) as exc:
        service.get_users(db, page_size=101)

    assert exc.value.status_code == 422
