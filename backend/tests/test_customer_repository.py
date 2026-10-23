
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.models
from app.db.session import Base
from app.models.customer import Customer
from app.repositories.customer_repository import CustomerRepository
from app.schemas.customer import CustomerCreate, CustomerUpdate


@pytest.fixture
def db():
    """Crea una base SQLite temporal para cada prueba."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)

    with Session(engine) as session:
        yield session
        session.rollback()

    engine.dispose()


@pytest.fixture
def repository(db):
    return CustomerRepository(db)


@pytest.fixture
def customer_data():
    return CustomerCreate(
        nombre="María",
        apellido="López",
        email="maria@ejemplo.com",
        telefono="9811234567",
        fecha_nacimiento=date(2000, 5, 15),
    )


@pytest.fixture
def saved_customer(repository, db, customer_data):
    customer = repository.create(customer_data)
    db.commit()
    return customer


# ============================================================
# CREATE
# ============================================================

def test_create_customer(repository, db, customer_data):
    customer = repository.create(customer_data)

    assert customer.id is not None
    assert customer.nombre == "María"
    assert customer.apellido == "López"
    assert customer.email == "maria@ejemplo.com"
    assert customer.telefono == "9811234567"
    assert customer.fecha_nacimiento == date(2000, 5, 15)
    assert customer.created_at is not None
    assert customer.activo is True

    db.commit()


def test_create_customer_with_optional_fields(repository):
    data = CustomerCreate(nombre="Carlos")

    customer = repository.create(data)

    assert customer.id is not None
    assert customer.nombre == "Carlos"
    assert customer.apellido is None
    assert customer.email is None
    assert customer.telefono is None
    assert customer.fecha_nacimiento is None
    assert customer.usuario_id is None
    assert customer.activo is True


# ============================================================
# READ
# ============================================================

def test_get_customer_by_id(repository, saved_customer):
    result = repository.get_by_id(saved_customer.id)

    assert result is not None
    assert result.id == saved_customer.id
    assert result.nombre == "María"
    assert result.activo is True


def test_get_nonexistent_customer(repository):
    result = repository.get_by_id(999)

    assert result is None


def test_get_customer_by_email(repository, saved_customer):
    result = repository.get_by_email(
        "maria@ejemplo.com"
    )

    assert len(result) == 1
    assert result[0].id == saved_customer.id


def test_get_customer_by_email_case_insensitive(
    repository,
    saved_customer,
):
    result = repository.get_by_email(
        "MARIA@EJEMPLO.COM"
    )

    assert len(result) == 1
    assert result[0].id == saved_customer.id


def test_get_nonexistent_customer_by_email(repository):
    result = repository.get_by_email(
        "noexiste@ejemplo.com"
    )

    assert result == []


def test_get_customer_by_user_id_not_found(repository):
    result = repository.get_by_user_id(999)

    assert result is None


def test_get_inactive_customer_by_id(
    repository,
    saved_customer,
):
    """Los clientes inactivos siguen siendo consultables."""

    customer_id = saved_customer.id

    repository.deactivate(saved_customer)

    result = repository.get_by_id(customer_id)

    assert result is not None
    assert result.id == customer_id
    assert result.activo is False


# ============================================================
# LIST / PAGINATION
# ============================================================

def test_get_all_customers(repository, saved_customer):
    customers = repository.get_all()

    assert len(customers) == 1
    assert customers[0].id == saved_customer.id


def test_get_all_customers_empty(repository):
    customers = repository.get_all()

    assert customers == []


def test_get_all_customers_with_pagination(repository):
    for i in range(5):
        repository.create(
            CustomerCreate(nombre=f"Cliente {i}")
        )

    first_page = repository.get_all(
        skip=0,
        limit=2,
    )

    second_page = repository.get_all(
        skip=2,
        limit=2,
    )

    assert len(first_page) == 2
    assert len(second_page) == 2

    first_ids = {customer.id for customer in first_page}
    second_ids = {customer.id for customer in second_page}

    assert first_ids.isdisjoint(second_ids)


def test_get_all_active_customers(repository):
    """Filtra únicamente clientes activos."""

    active = repository.create(
        CustomerCreate(nombre="Cliente Activo")
    )

    inactive = repository.create(
        CustomerCreate(nombre="Cliente Inactivo")
    )

    repository.deactivate(inactive)

    customers = repository.get_all(
        solo_activos=True
    )

    assert len(customers) == 1
    assert customers[0].id == active.id
    assert customers[0].activo is True


def test_get_all_inactive_customers(repository):
    """Filtra únicamente clientes inactivos."""

    active = repository.create(
        CustomerCreate(nombre="Cliente Activo")
    )

    inactive = repository.create(
        CustomerCreate(nombre="Cliente Inactivo")
    )

    repository.deactivate(inactive)

    customers = repository.get_all(
        solo_activos=False
    )

    assert len(customers) == 1
    assert customers[0].id == inactive.id
    assert customers[0].activo is False
    assert customers[0].id != active.id


def test_get_all_customers_without_status_filter(repository):
    """Sin filtro se incluyen activos e inactivos."""

    repository.create(
        CustomerCreate(nombre="Cliente Activo")
    )

    inactive = repository.create(
        CustomerCreate(nombre="Cliente Inactivo")
    )

    repository.deactivate(inactive)

    customers = repository.get_all(
        solo_activos=None
    )

    assert len(customers) == 2

    statuses = {customer.activo for customer in customers}

    assert statuses == {True, False}


def test_get_all_active_customers_with_pagination(repository):
    """La paginación se aplica después del filtro."""

    for i in range(5):
        customer = repository.create(
            CustomerCreate(nombre=f"Cliente {i}")
        )

        if i in (1, 3):
            repository.deactivate(customer)

    customers = repository.get_all(
        skip=1,
        limit=2,
        solo_activos=True,
    )

    assert len(customers) == 2
    assert all(customer.activo for customer in customers)


# ============================================================
# COUNT
# ============================================================

def test_count_customers_empty(repository):
    assert repository.count() == 0


def test_count_customers(repository):
    for i in range(3):
        repository.create(
            CustomerCreate(nombre=f"Cliente {i}")
        )

    assert repository.count() == 3


def test_count_active_customers(repository):
    """Cuenta únicamente los clientes activos."""

    repository.create(
        CustomerCreate(nombre="Cliente Activo")
    )

    inactive = repository.create(
        CustomerCreate(nombre="Cliente Inactivo")
    )

    repository.deactivate(inactive)

    assert repository.count(solo_activos=True) == 1


def test_count_inactive_customers(repository):
    """Cuenta únicamente los clientes inactivos."""

    repository.create(
        CustomerCreate(nombre="Cliente Activo")
    )

    inactive = repository.create(
        CustomerCreate(nombre="Cliente Inactivo")
    )

    repository.deactivate(inactive)

    assert repository.count(solo_activos=False) == 1


def test_count_all_customers_including_inactive(repository):
    """El conteo general incluye clientes inactivos."""

    repository.create(
        CustomerCreate(nombre="Cliente Activo")
    )

    inactive = repository.create(
        CustomerCreate(nombre="Cliente Inactivo")
    )

    repository.deactivate(inactive)

    assert repository.count() == 2


# ============================================================
# UPDATE
# ============================================================

def test_update_customer(repository, saved_customer):
    data = CustomerUpdate(
        nombre="María Fernanda",
        telefono="9819876543",
    )

    updated = repository.update(
        saved_customer,
        data,
    )

    assert updated.id == saved_customer.id
    assert updated.nombre == "María Fernanda"
    assert updated.telefono == "9819876543"
    assert updated.email == "maria@ejemplo.com"
    assert updated.activo is True


def test_update_customer_nullable_field(
    repository,
    saved_customer,
):
    data = CustomerUpdate(
        telefono=None
    )

    updated = repository.update(
        saved_customer,
        data,
    )

    assert updated.telefono is None
    assert updated.nombre == "María"


# ============================================================
# SOFT DELETE / DEACTIVATE / REACTIVATE
# ============================================================

def test_delete_customer(repository, saved_customer):
    """delete() desactiva sin eliminar físicamente."""

    customer_id = saved_customer.id

    repository.delete(saved_customer)

    result = repository.get_by_id(customer_id)

    assert result is not None
    assert result.id == customer_id
    assert result.activo is False


def test_deactivate_customer(repository, saved_customer):
    """Desactiva un cliente conservando su registro."""

    assert saved_customer.activo is True

    result = repository.deactivate(saved_customer)

    assert result.id == saved_customer.id
    assert result.activo is False

    stored_customer = repository.get_by_id(
        saved_customer.id
    )

    assert stored_customer is not None
    assert stored_customer.activo is False


def test_reactivate_customer(repository, saved_customer):
    """Reactiva un cliente previamente desactivado."""

    repository.deactivate(saved_customer)

    assert saved_customer.activo is False

    result = repository.reactivate(saved_customer)

    assert result.id == saved_customer.id
    assert result.activo is True

    stored_customer = repository.get_by_id(
        saved_customer.id
    )

    assert stored_customer is not None
    assert stored_customer.activo is True


def test_deactivate_customer_preserves_data(
    repository,
    saved_customer,
):
    """La desactivación conserva los datos del cliente."""

    customer_id = saved_customer.id
    original_name = saved_customer.nombre
    original_email = saved_customer.email

    repository.deactivate(saved_customer)

    customer = repository.get_by_id(customer_id)

    assert customer is not None
    assert customer.activo is False
    assert customer.nombre == original_name
    assert customer.email == original_email


def test_deactivate_customer_persists_after_commit(
    repository,
    db,
    saved_customer,
):
    """El estado inactivo persiste tras confirmar la transacción."""

    customer_id = saved_customer.id

    repository.deactivate(saved_customer)

    db.commit()
    db.expire_all()

    customer = repository.get_by_id(customer_id)

    assert customer is not None
    assert customer.activo is False


def test_reactivate_customer_persists_after_commit(
    repository,
    db,
    saved_customer,
):
    """El estado activo persiste tras confirmar la transacción."""

    customer_id = saved_customer.id

    repository.deactivate(saved_customer)
    db.commit()

    repository.reactivate(saved_customer)
    db.commit()
    db.expire_all()

    customer = repository.get_by_id(customer_id)

    assert customer is not None
    assert customer.activo is True


# ============================================================
# USER ASSOCIATION
# ============================================================

def test_user_association_not_found(repository):
    exists = repository.exists_by_user_id(999)

    assert exists is False


def test_user_association_with_exclusion(repository):
    exists = repository.exists_by_user_id(
        999,
        exclude_customer_id=1,
    )

    assert exists is False


# ============================================================
# MODEL
# ============================================================

def test_customer_model_table_name():
    assert Customer.__tablename__ == "clientes"


def test_customer_model_has_active_column():
    """Verifica que el modelo incluye la columna activo."""

    column = Customer.__table__.columns["activo"]

    assert column.name == "activo"
    assert column.nullable is False
