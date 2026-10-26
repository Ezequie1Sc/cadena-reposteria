
"""Pruebas de la lógica de negocio del módulo de usuarios."""

import pytest

from fastapi import HTTPException
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import verify_password
from app.db.session import Base
from app.modules.users.model import User
from app.modules.users.schemas import UserCreate, UserUpdate
from app.modules.users.service import UserService
from app.shared.models.role_reference import roles_reference


PASSWORD = "PasswordSegura2026!"
NEW_PASSWORD = "NuevaPasswordSegura2026!"


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

    with engine.begin() as connection:
        connection.exec_driver_sql(
            "ALTER TABLE roles "
            "ADD COLUMN activo BOOLEAN NOT NULL DEFAULT 1"
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
        password=PASSWORD,
        telefono="9991234567",
    )


@pytest.fixture
def created_user(db, service, user_data):
    return service.create_user(db, user_data)


@pytest.fixture
def second_admin(db, service):
    """Crea un segundo administrador activo."""

    return service.create_user(
        db,
        UserCreate(
            rol_id=1,
            nombre="Carlos",
            apellido="Pérez",
            email="carlos.admin@example.com",
            password=PASSWORD,
        ),
    )


def activate_employee_role(db):
    """Activa el rol Empleado para probar cambios de rol."""

    db.execute(
        text("UPDATE roles SET activo = 1 WHERE id = 2")
    )
    db.commit()


def assert_http_error(expected_status, operation):
    """Verifica el código HTTP de una operación rechazada."""

    with pytest.raises(HTTPException) as exc:
        operation()

    assert exc.value.status_code == expected_status


# ============================================================
# CREACIÓN DE USUARIOS
# ============================================================


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
    assert_http_error(
        409,
        lambda: service.create_user(db, user_data),
    )


def test_create_user_rejects_inactive_role(db, service):
    data = UserCreate(
        rol_id=2,
        nombre="Carlos",
        apellido="Pérez",
        email="carlos@example.com",
        password=PASSWORD,
    )

    assert_http_error(
        422,
        lambda: service.create_user(db, data),
    )


def test_create_user_rejects_missing_role(db, service):
    data = UserCreate(
        rol_id=999,
        nombre="Carlos",
        apellido="Pérez",
        email="carlos@example.com",
        password=PASSWORD,
    )

    assert_http_error(
        422,
        lambda: service.create_user(db, data),
    )


# ============================================================
# CONSULTAS
# ============================================================


def test_get_user_by_id(db, service, created_user):
    result = service.get_user_by_id(db, created_user.id)

    assert result.id == created_user.id
    assert result.nombre == "Ana"


def test_get_user_by_id_returns_404(db, service):
    assert_http_error(
        404,
        lambda: service.get_user_by_id(db, 999),
    )


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
    assert_http_error(
        422,
        lambda: service.get_users(db, page=0),
    )


def test_get_users_rejects_invalid_page_size(db, service):
    assert_http_error(
        422,
        lambda: service.get_users(db, page_size=101),
    )


# ============================================================
# ACTUALIZACIÓN DE USUARIOS
# ============================================================


def test_update_user(db, service, created_user):
    result = service.update_user(
        db,
        created_user.id,
        UserUpdate(nombre="María"),
        actor_id=created_user.id,
    )

    assert result.nombre == "María"
    assert result.email == "ana@example.com"


def test_update_password(db, service, created_user):
    service.update_user(
        db,
        created_user.id,
        UserUpdate(password=NEW_PASSWORD),
        actor_id=created_user.id,
    )

    user = db.get(User, created_user.id)

    assert verify_password(
        NEW_PASSWORD,
        user.password_hash,
    )
    assert not verify_password(
        PASSWORD,
        user.password_hash,
    )


def test_update_rejects_null_required_field(
    db, service, created_user
):
    assert_http_error(
        422,
        lambda: service.update_user(
            db,
            created_user.id,
            UserUpdate(nombre=None),
            actor_id=created_user.id,
        ),
    )


# ============================================================
# DESACTIVACIÓN Y REACTIVACIÓN
# ============================================================


def test_deactivate_user(
    db,
    service,
    created_user,
    second_admin,
):
    result = service.deactivate_user(
        db,
        second_admin.id,
        actor_id=created_user.id,
    )

    assert result.activo is False


def test_reactivate_user(
    db,
    service,
    created_user,
    second_admin,
):
    service.deactivate_user(
        db,
        second_admin.id,
        actor_id=created_user.id,
    )

    result = service.reactivate_user(
        db,
        second_admin.id,
    )

    assert result.activo is True


# ============================================================
# SEGURIDAD: AUTODESACTIVACIÓN
# ============================================================


def test_admin_cannot_deactivate_self(
    db,
    service,
    created_user,
):
    """Un administrador no puede desactivar su propia cuenta."""

    assert_http_error(
        403,
        lambda: service.deactivate_user(
            db,
            created_user.id,
            actor_id=created_user.id,
        ),
    )

    db.refresh(db.get(User, created_user.id))

    assert db.get(User, created_user.id).activo is True


def test_admin_cannot_deactivate_self_with_other_admin(
    db,
    service,
    created_user,
    second_admin,
):
    """La autodesactivación sigue prohibida aunque existan otros."""

    assert_http_error(
        403,
        lambda: service.deactivate_user(
            db,
            created_user.id,
            actor_id=created_user.id,
        ),
    )

    assert db.get(User, created_user.id).activo is True
    assert db.get(User, second_admin.id).activo is True


# ============================================================
# SEGURIDAD: CAMBIO DEL PROPIO ROL
# ============================================================


def test_admin_cannot_change_own_role(
    db,
    service,
    created_user,
    second_admin,
):
    """Un administrador no puede quitarse sus propios permisos."""

    activate_employee_role(db)

    assert_http_error(
        403,
        lambda: service.update_user(
            db,
            created_user.id,
            UserUpdate(rol_id=2),
            actor_id=created_user.id,
        ),
    )

    db.refresh(db.get(User, created_user.id))

    assert db.get(User, created_user.id).rol_id == 1


def test_admin_can_update_own_personal_data(
    db,
    service,
    created_user,
):
    """Un administrador puede modificar sus datos personales."""

    result = service.update_user(
        db,
        created_user.id,
        UserUpdate(
            nombre="Ana María",
            telefono="9998887777",
        ),
        actor_id=created_user.id,
    )

    assert result.nombre == "Ana María"
    assert result.telefono == "9998887777"
    assert result.rol_id == 1


# ============================================================
# SEGURIDAD: ÚLTIMO ADMINISTRADOR
# ============================================================


def test_cannot_deactivate_last_active_admin(
    db,
    service,
    created_user,
    second_admin,
):
    """No se permite dejar el sistema sin administradores."""

    service.deactivate_user(
        db,
        second_admin.id,
        actor_id=created_user.id,
    )

    assert_http_error(
        409,
        lambda: service.deactivate_user(
            db,
            created_user.id,
            actor_id=second_admin.id,
        ),
    )

    assert db.get(User, created_user.id).activo is True


def test_cannot_remove_last_active_admin_role(
    db,
    service,
    created_user,
    second_admin,
):
    """El último administrador no puede perder su rol."""

    activate_employee_role(db)

    service.deactivate_user(
        db,
        second_admin.id,
        actor_id=created_user.id,
    )

    assert_http_error(
        409,
        lambda: service.update_user(
            db,
            created_user.id,
            UserUpdate(rol_id=2),
            actor_id=second_admin.id,
        ),
    )

    db.refresh(db.get(User, created_user.id))

    assert db.get(User, created_user.id).rol_id == 1


def test_admin_can_change_another_admin_role(
    db,
    service,
    created_user,
    second_admin,
):
    """Se permite cambiar el rol si queda otro administrador."""

    activate_employee_role(db)

    result = service.update_user(
        db,
        second_admin.id,
        UserUpdate(rol_id=2),
        actor_id=created_user.id,
    )

    assert result.rol_id == 2
    assert db.get(User, created_user.id).rol_id == 1


def test_admin_can_deactivate_another_admin(
    db,
    service,
    created_user,
    second_admin,
):
    """Se permite desactivar a otro administrador si no es el último."""

    result = service.deactivate_user(
        db,
        second_admin.id,
        actor_id=created_user.id,
    )

    assert result.activo is False
    assert db.get(User, created_user.id).activo is True


# ============================================================
# SEGURIDAD: IDENTIDAD DEL ACTOR
# ============================================================


@pytest.mark.parametrize(
    "actor_id",
    [0, -1, True],
)
def test_update_rejects_invalid_actor(
    db,
    service,
    created_user,
    actor_id,
):
    """Se rechazan identificadores administrativos inválidos."""

    assert_http_error(
        403,
        lambda: service.update_user(
            db,
            created_user.id,
            UserUpdate(nombre="Cambio"),
            actor_id=actor_id,
        ),
    )


@pytest.mark.parametrize(
    "actor_id",
    [0, -1, True],
)
def test_deactivate_rejects_invalid_actor(
    db,
    service,
    created_user,
    actor_id,
):
    """No se permite desactivar sin identidad administrativa válida."""

    assert_http_error(
        403,
        lambda: service.deactivate_user(
            db,
            created_user.id,
            actor_id=actor_id,
        ),
    )
