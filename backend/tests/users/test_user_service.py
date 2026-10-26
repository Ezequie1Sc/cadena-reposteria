
"""Pruebas de la lógica de negocio del módulo de usuarios."""

import pytest

from fastapi import HTTPException
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password, verify_password
from app.db.session import Base
from app.modules.users.model import User
from app.modules.users.schemas import UserCreate, UserUpdate
from app.modules.users.service import UserService
from app.shared.models.role_reference import roles_reference


PASSWORD = "PasswordSegura2026!"
NEW_PASSWORD = "NuevaPasswordSegura2026!"


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

    with engine.begin() as connection:
        connection.exec_driver_sql(
            "ALTER TABLE roles "
            "ADD COLUMN activo BOOLEAN NOT NULL DEFAULT 1"
        )

        connection.exec_driver_sql(
            "INSERT INTO roles (id, activo) "
            "VALUES (1, 1), (2, 0), (3, 1)"
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
    """Devuelve una instancia del servicio de usuarios."""
    return UserService()


@pytest.fixture
def user_data():
    """Datos válidos para crear un administrador."""

    return UserCreate(
        rol_id=1,
        nombre="Ana",
        apellido="López",
        email="ana@example.com",
        password=PASSWORD,
        telefono="9991234567",
    )


@pytest.fixture
def created_user(db, user_data):
    """Inicializa el primer administrador sin depender del servicio."""

    user = User(
        rol_id=1,
        nombre=user_data.nombre,
        apellido=user_data.apellido,
        email=user_data.email,
        telefono=user_data.telefono,
        password_hash=hash_password(user_data.password),
        activo=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@pytest.fixture
def second_admin(db, service, created_user):
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
        actor_id=created_user.id,
    )


@pytest.fixture
def employee(db, service, created_user):
    """Crea un empleado activo para pruebas de autorización."""

    db.execute(
        text("UPDATE roles SET activo = 1 WHERE id = 2")
    )
    db.commit()

    return service.create_user(
        db,
        UserCreate(
            rol_id=2,
            nombre="Pedro",
            apellido="Gómez",
            email="pedro@example.com",
            password=PASSWORD,
        ),
        actor_id=created_user.id,
    )


@pytest.fixture
def customer(db, service, created_user):
    """Crea un cliente activo para pruebas de autorización."""

    return service.create_user(
        db,
        UserCreate(
            rol_id=3,
            nombre="Laura",
            apellido="Martínez",
            email="laura@example.com",
            password=PASSWORD,
        ),
        actor_id=created_user.id,
    )


# ============================================================
# HELPERS
# ============================================================


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


def test_create_user_hashes_password(
    db,
    service,
    user_data,
    created_user,
):
    """La contraseña se almacena como hash Argon2id."""

    data = user_data.model_copy(
        update={"email": "ana.nueva@example.com"}
    )

    result = service.create_user(
        db,
        data,
        actor_id=created_user.id,
    )

    user = db.get(User, result.id)

    assert result.email == "ana.nueva@example.com"
    assert user is not None
    assert user.password_hash != user_data.password
    assert user.password_hash.startswith("$argon2id$")
    assert verify_password(
        user_data.password,
        user.password_hash,
    )


def test_user_response_does_not_expose_password(
    db,
    service,
    created_user,
):
    """Las respuestas públicas no contienen contraseñas."""

    response = service.get_user_by_id(
        db,
        created_user.id,
    )

    data = response.model_dump()

    assert "password_hash" not in data
    assert "password" not in data


def test_create_user_rejects_duplicate_email(
    db,
    service,
    user_data,
    created_user,
):
    """No se permiten correos duplicados."""

    assert_http_error(
        409,
        lambda: service.create_user(
            db,
            user_data,
            actor_id=created_user.id,
        ),
    )


def test_create_user_rejects_inactive_role(
    db,
    service,
    created_user,
):
    """No se permite crear usuarios con roles inactivos."""

    data = UserCreate(
        rol_id=2,
        nombre="Carlos",
        apellido="Pérez",
        email="carlos@example.com",
        password=PASSWORD,
    )

    assert_http_error(
        422,
        lambda: service.create_user(db, data, actor_id=created_user.id),
    )


def test_create_user_rejects_missing_role(
    db,
    service,
    created_user,
):
    """No se permite utilizar un rol inexistente."""

    data = UserCreate(
        rol_id=999,
        nombre="Carlos",
        apellido="Pérez",
        email="carlos@example.com",
        password=PASSWORD,
    )

    assert_http_error(
        422,
        lambda: service.create_user(db, data, actor_id=created_user.id),
    )


# ============================================================
# CONSULTAS DE USUARIOS
# ============================================================


def test_get_user_by_id(
    db,
    service,
    created_user,
):
    """Permite consultar un usuario existente."""

    result = service.get_user_by_id(
        db,
        created_user.id,
    )

    assert result.id == created_user.id
    assert result.nombre == "Ana"


def test_get_user_by_id_returns_404(
    db,
    service,
):
    """Devuelve 404 para usuarios inexistentes."""

    assert_http_error(
        404,
        lambda: service.get_user_by_id(
            db,
            999,
        ),
    )


def test_get_users_filters_by_search(
    db,
    service,
    created_user,
):
    """Permite buscar usuarios por correo electrónico."""

    result = service.get_users(
        db,
        busqueda="ana@example.com",
    )

    assert result["total"] == 1
    assert len(result["items"]) == 1
    assert result["items"][0].id == created_user.id


def test_get_users_search_without_matches(
    db,
    service,
    created_user,
):
    """Devuelve un listado vacío cuando no hay coincidencias."""

    result = service.get_users(
        db,
        busqueda="noexiste@example.com",
    )

    assert result["total"] == 0
    assert result["items"] == []


def test_get_users_pagination(
    db,
    service,
    created_user,
):
    """Aplica correctamente la paginación."""

    result = service.get_users(
        db,
        page=1,
        page_size=1,
    )

    assert result["total"] == 1
    assert len(result["items"]) == 1
    assert result["page"] == 1
    assert result["page_size"] == 1


def test_get_users_rejects_invalid_page(
    db,
    service,
):
    """Rechaza números de página inválidos."""

    assert_http_error(
        422,
        lambda: service.get_users(
            db,
            page=0,
        ),
    )


def test_get_users_rejects_invalid_page_size(
    db,
    service,
):
    """Rechaza tamaños de página fuera del límite."""

    assert_http_error(
        422,
        lambda: service.get_users(
            db,
            page_size=101,
        ),
    )


# ============================================================
# ACTUALIZACIÓN DE USUARIOS
# ============================================================


def test_update_user(
    db,
    service,
    created_user,
):
    """Permite actualizar datos personales."""

    result = service.update_user(
        db,
        created_user.id,
        UserUpdate(nombre="María"),
        actor_id=created_user.id,
    )

    assert result.nombre == "María"
    assert result.email == "ana@example.com"


def test_update_password(
    db,
    service,
    created_user,
):
    """La actualización de contraseña genera un nuevo hash."""

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
    db,
    service,
    created_user,
):
    """Los campos obligatorios no admiten valores nulos."""

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
    """Un administrador puede desactivar a otro."""

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
    """Permite reactivar una cuenta desactivada."""

    service.deactivate_user(
        db,
        second_admin.id,
        actor_id=created_user.id,
    )

    result = service.reactivate_user(
        db,
        second_admin.id,
        actor_id=created_user.id,
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
    """Un administrador no puede desactivar su cuenta."""

    assert_http_error(
        403,
        lambda: service.deactivate_user(
            db,
            created_user.id,
            actor_id=created_user.id,
        ),
    )

    user = db.get(User, created_user.id)

    assert user.activo is True


def test_admin_cannot_deactivate_self_with_other_admin(
    db,
    service,
    created_user,
    second_admin,
):
    """La autodesactivación está prohibida incluso con otros administradores."""

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
    """Un administrador no puede cambiar su propio rol."""

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

    user = db.get(User, created_user.id)

    assert user.rol_id == 1


def test_admin_can_update_own_personal_data(
    db,
    service,
    created_user,
):
    """Un administrador puede actualizar sus datos personales."""

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
    """
    Un administrador inactivo no puede desactivar
    al único administrador activo.
    """

    service.deactivate_user(
        db,
        second_admin.id,
        actor_id=created_user.id,
    )

    assert_http_error(
        403,
        lambda: service.deactivate_user(
            db,
            created_user.id,
            actor_id=second_admin.id,
        ),
    )

    user = db.get(User, created_user.id)

    assert user.activo is True


def test_cannot_remove_last_active_admin_role(
    db,
    service,
    created_user,
    second_admin,
):
    """
    Un administrador inactivo no puede retirar
    el rol del último administrador activo.
    """

    activate_employee_role(db)

    service.deactivate_user(
        db,
        second_admin.id,
        actor_id=created_user.id,
    )

    assert_http_error(
        403,
        lambda: service.update_user(
            db,
            created_user.id,
            UserUpdate(rol_id=2),
            actor_id=second_admin.id,
        ),
    )

    user = db.get(User, created_user.id)

    assert user.rol_id == 1


def test_admin_can_change_another_admin_role(
    db,
    service,
    created_user,
    second_admin,
):
    """Puede cambiar el rol de otro administrador si queda uno activo."""

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
    """Puede desactivar a otro administrador si queda uno activo."""

    result = service.deactivate_user(
        db,
        second_admin.id,
        actor_id=created_user.id,
    )

    assert result.activo is False
    assert db.get(User, created_user.id).activo is True


# ============================================================
# SEGURIDAD: IDENTIFICADORES INVÁLIDOS
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
    """Rechaza identificadores inválidos al actualizar."""

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
    """Rechaza identificadores inválidos al desactivar."""

    assert_http_error(
        403,
        lambda: service.deactivate_user(
            db,
            created_user.id,
            actor_id=actor_id,
        ),
    )


# ============================================================
# SEGURIDAD: ADMINISTRADORES INACTIVOS
# ============================================================


def test_inactive_admin_cannot_update_user(
    db,
    service,
    created_user,
    second_admin,
):
    """Un administrador desactivado no puede actualizar usuarios."""

    service.deactivate_user(
        db,
        second_admin.id,
        actor_id=created_user.id,
    )

    assert_http_error(
        403,
        lambda: service.update_user(
            db,
            created_user.id,
            UserUpdate(nombre="Cambio prohibido"),
            actor_id=second_admin.id,
        ),
    )

    assert db.get(User, created_user.id).nombre == "Ana"


def test_nonexistent_actor_cannot_update_user(
    db,
    service,
    created_user,
):
    """Un usuario inexistente no puede ejecutar operaciones."""

    assert_http_error(
        403,
        lambda: service.update_user(
            db,
            created_user.id,
            UserUpdate(nombre="Cambio prohibido"),
            actor_id=999999,
        ),
    )

    assert db.get(User, created_user.id).nombre == "Ana"


def test_inactive_admin_role_blocks_updates(
    db,
    service,
    created_user,
):
    """Un rol Administrador inactivo impide actualizar usuarios."""

    db.execute(
        text(
            "UPDATE roles "
            "SET activo = 0 "
            "WHERE id = 1"
        )
    )
    db.commit()

    assert_http_error(
        403,
        lambda: service.update_user(
            db,
            created_user.id,
            UserUpdate(nombre="Cambio prohibido"),
            actor_id=created_user.id,
        ),
    )

    assert db.get(User, created_user.id).nombre == "Ana"


# ============================================================
# SEGURIDAD: EMPLEADOS Y CLIENTES
# ============================================================


@pytest.mark.parametrize(
    "role_fixture",
    ["employee", "customer"],
)
def test_non_admin_cannot_update_user(
    db,
    service,
    created_user,
    role_fixture,
    request,
):
    """Empleados y clientes no pueden actualizar usuarios."""

    non_admin = request.getfixturevalue(role_fixture)

    assert_http_error(
        403,
        lambda: service.update_user(
            db,
            created_user.id,
            UserUpdate(nombre="Cambio prohibido"),
            actor_id=non_admin.id,
        ),
    )

    assert db.get(User, created_user.id).nombre == "Ana"


@pytest.mark.parametrize(
    "role_fixture",
    ["employee", "customer"],
)
def test_non_admin_cannot_deactivate_user(
    db,
    service,
    created_user,
    role_fixture,
    request,
):
    """Empleados y clientes no pueden desactivar usuarios."""

    non_admin = request.getfixturevalue(role_fixture)

    assert_http_error(
        403,
        lambda: service.deactivate_user(
            db,
            created_user.id,
            actor_id=non_admin.id,
        ),
    )

    assert db.get(User, created_user.id).activo is True


# ============================================================
# SEGURIDAD: CREACI?N Y REACTIVACI?N ADMINISTRATIVA
# ============================================================


def administrative_user_payload(email="nuevo.seguridad@example.com"):
    """Datos de prueba para operaciones administrativas."""

    return UserCreate(
        rol_id=3,
        nombre="Nuevo",
        apellido="Usuario",
        email=email,
        password=PASSWORD,
    )


def deactivate_test_account(db, user):
    """Prepara una cuenta inactiva sin depender de permisos HTTP."""

    user.activo = False
    db.commit()
    db.refresh(user)


@pytest.mark.parametrize("actor_id", [0, -1, True])
def test_create_rejects_invalid_actor(
    db,
    service,
    created_user,
    actor_id,
):
    """La creaci?n rechaza identificadores administrativos inv?lidos."""

    assert_http_error(
        403,
        lambda: service.create_user(
            db,
            administrative_user_payload(),
            actor_id=actor_id,
        ),
    )

    assert service.get_users(db)["total"] == 1


@pytest.mark.parametrize("actor_id", [0, -1, True])
def test_reactivate_rejects_invalid_actor(
    db,
    service,
    created_user,
    customer,
    actor_id,
):
    """La reactivaci?n rechaza identificadores inv?lidos."""

    target = db.get(User, customer.id)
    deactivate_test_account(db, target)

    assert_http_error(
        403,
        lambda: service.reactivate_user(
            db,
            target.id,
            actor_id=actor_id,
        ),
    )

    db.refresh(target)
    assert target.activo is False


@pytest.mark.parametrize("role_fixture", ["employee", "customer"])
def test_non_admin_cannot_create_user(
    db,
    service,
    created_user,
    role_fixture,
    request,
):
    """Empleados y clientes no pueden crear cuentas administrativamente."""

    actor = request.getfixturevalue(role_fixture)
    total_before = service.get_users(db)["total"]

    assert_http_error(
        403,
        lambda: service.create_user(
            db,
            administrative_user_payload(),
            actor_id=actor.id,
        ),
    )

    assert service.get_users(db)["total"] == total_before


@pytest.mark.parametrize("role_fixture", ["employee", "customer"])
def test_non_admin_cannot_reactivate_user(
    db,
    service,
    created_user,
    role_fixture,
    request,
):
    """Empleados y clientes no pueden reactivar cuentas."""

    actor = request.getfixturevalue(role_fixture)

    target = db.get(User, created_user.id)

    # Se crea una cuenta adicional que actuar? como objetivo.
    target_data = administrative_user_payload(
        "objetivo.reactivar@example.com"
    )
    result = service.create_user(
        db,
        target_data,
        actor_id=created_user.id,
    )

    target = db.get(User, result.id)
    deactivate_test_account(db, target)

    assert_http_error(
        403,
        lambda: service.reactivate_user(
            db,
            target.id,
            actor_id=actor.id,
        ),
    )

    db.refresh(target)
    assert target.activo is False


def test_inactive_admin_cannot_create_user(
    db,
    service,
    created_user,
    second_admin,
):
    """Una cuenta administrativa desactivada no puede crear usuarios."""

    actor = db.get(User, second_admin.id)
    deactivate_test_account(db, actor)

    assert_http_error(
        403,
        lambda: service.create_user(
            db,
            administrative_user_payload(),
            actor_id=actor.id,
        ),
    )


def test_inactive_admin_cannot_reactivate_user(
    db,
    service,
    created_user,
    second_admin,
    customer,
):
    """Una cuenta administrativa desactivada no puede reactivar usuarios."""

    actor = db.get(User, second_admin.id)
    target = db.get(User, customer.id)

    deactivate_test_account(db, actor)
    deactivate_test_account(db, target)

    assert_http_error(
        403,
        lambda: service.reactivate_user(
            db,
            target.id,
            actor_id=actor.id,
        ),
    )

    db.refresh(target)
    assert target.activo is False


def test_inactive_admin_role_blocks_creation(
    db,
    service,
    created_user,
):
    """La creaci?n falla cuando el rol Administrador est? inactivo."""

    db.execute(
        text("UPDATE roles SET activo = 0 WHERE id = 1")
    )
    db.commit()

    assert_http_error(
        403,
        lambda: service.create_user(
            db,
            administrative_user_payload(),
            actor_id=created_user.id,
        ),
    )


def test_inactive_admin_role_blocks_reactivation(
    db,
    service,
    created_user,
    customer,
):
    """La reactivaci?n falla cuando el rol Administrador est? inactivo."""

    target = db.get(User, customer.id)
    deactivate_test_account(db, target)

    db.execute(
        text("UPDATE roles SET activo = 0 WHERE id = 1")
    )
    db.commit()

    assert_http_error(
        403,
        lambda: service.reactivate_user(
            db,
            target.id,
            actor_id=created_user.id,
        ),
    )

    db.refresh(target)
    assert target.activo is False
