
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.modules.customers.schemas import CustomerCreate, CustomerUpdate
from app.modules.customers.service import (
    CustomerConflictError,
    CustomerNotFoundError,
    CustomerService,
    CustomerValidationError,
)


@pytest.fixture
def db():
    """Sesión de base de datos simulada."""
    return MagicMock()


@pytest.fixture
def service(db):
    """Instancia del servicio de clientes."""
    return CustomerService(db)


@pytest.fixture
def customer():
    """Cliente activo simulado para las pruebas."""
    obj = MagicMock()
    obj.id = 1
    obj.nombre = "María"
    obj.apellido = "López"
    obj.email = "maria@ejemplo.com"
    obj.usuario_id = None
    obj.activo = True
    return obj


# ============================================================
# CREATE
# ============================================================

def test_create_customer(service, db, customer):
    data = CustomerCreate(
        nombre="María",
        apellido="López",
        email="maria@ejemplo.com",
    )

    service.repository.create = MagicMock(
        return_value=customer
    )

    result = service.create(data)

    assert result.id == 1
    assert result.activo is True

    service.repository.create.assert_called_once_with(data)

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(customer)


def test_create_customer_with_duplicate_user(service, db):
    data = CustomerCreate(
        nombre="Carlos",
        usuario_id=5,
    )

    db.scalar.return_value = 5

    service.repository.exists_by_user_id = MagicMock(
        return_value=True
    )

    with pytest.raises(
        CustomerConflictError,
        match="ya está asociado",
    ):
        service.create(data)

    service.repository.exists_by_user_id.assert_called_once_with(
        5,
        exclude_customer_id=None,
    )

    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_create_customer_with_nonexistent_user(service, db):
    data = CustomerCreate(
        nombre="Carlos",
        usuario_id=999,
    )

    db.scalar.return_value = None

    with pytest.raises(
        CustomerValidationError,
        match="no existe",
    ):
        service.create(data)

    db.rollback.assert_called_once()
    db.commit.assert_not_called()


# ============================================================
# READ
# ============================================================

def test_get_customer_by_id(service, customer):
    service.repository.get_by_id = MagicMock(
        return_value=customer
    )

    result = service.get_by_id(1)

    assert result.id == 1
    assert result.nombre == "María"
    assert result.activo is True

    service.repository.get_by_id.assert_called_once_with(1)


def test_get_nonexistent_customer(service):
    service.repository.get_by_id = MagicMock(
        return_value=None
    )

    with pytest.raises(
        CustomerNotFoundError,
        match="no existe",
    ):
        service.get_by_id(999)

    service.repository.get_by_id.assert_called_once_with(999)


def test_get_inactive_customer_by_id(service, customer):
    """Un cliente inactivo sigue siendo consultable."""

    customer.activo = False

    service.repository.get_by_id = MagicMock(
        return_value=customer
    )

    result = service.get_by_id(1)

    assert result.id == 1
    assert result.activo is False


# ============================================================
# LIST / PAGINATION
# ============================================================

def test_list_customers(service, customer):
    service.repository.get_all = MagicMock(
        return_value=[customer]
    )

    service.repository.count = MagicMock(
        return_value=1
    )

    result = service.get_all(
        page=1,
        page_size=20,
    )

    assert result["total"] == 1
    assert result["page"] == 1
    assert result["page_size"] == 20
    assert len(result["items"]) == 1
    assert result["items"][0].id == 1

    service.repository.get_all.assert_called_once_with(
        skip=0,
        limit=20,
        solo_activos=None,
    )

    service.repository.count.assert_called_once_with(
        solo_activos=None,
    )


def test_list_active_customers(service, customer):
    """Solicita únicamente clientes activos."""

    service.repository.get_all = MagicMock(
        return_value=[customer]
    )

    service.repository.count = MagicMock(
        return_value=1
    )

    result = service.get_all(
        page=1,
        page_size=20,
        solo_activos=True,
    )

    assert result["total"] == 1
    assert len(result["items"]) == 1

    service.repository.get_all.assert_called_once_with(
        skip=0,
        limit=20,
        solo_activos=True,
    )

    service.repository.count.assert_called_once_with(
        solo_activos=True,
    )


def test_list_inactive_customers(service, customer):
    """Solicita únicamente clientes inactivos."""

    customer.activo = False

    service.repository.get_all = MagicMock(
        return_value=[customer]
    )

    service.repository.count = MagicMock(
        return_value=1
    )

    result = service.get_all(
        solo_activos=False,
    )

    assert result["total"] == 1
    assert result["items"][0].activo is False

    service.repository.get_all.assert_called_once_with(
        skip=0,
        limit=20,
        solo_activos=False,
    )

    service.repository.count.assert_called_once_with(
        solo_activos=False,
    )


def test_list_customers_with_pagination(service):
    """Calcula correctamente el desplazamiento."""

    service.repository.get_all = MagicMock(
        return_value=[]
    )

    service.repository.count = MagicMock(
        return_value=0
    )

    result = service.get_all(
        page=3,
        page_size=10,
    )

    assert result["page"] == 3
    assert result["page_size"] == 10

    service.repository.get_all.assert_called_once_with(
        skip=20,
        limit=10,
        solo_activos=None,
    )


def test_list_customers_invalid_page(service):
    with pytest.raises(
        CustomerValidationError,
        match="página",
    ):
        service.get_all(page=0)


def test_list_customers_invalid_page_size(service):
    with pytest.raises(
        CustomerValidationError,
        match="tamaño de página",
    ):
        service.get_all(page_size=101)


# ============================================================
# SEARCH
# ============================================================

def test_search_customers_by_email(service, customer):
    service.repository.get_by_email = MagicMock(
        return_value=[customer]
    )

    result = service.get_by_email(
        " maria@ejemplo.com "
    )

    assert len(result) == 1
    assert result[0].email == "maria@ejemplo.com"

    service.repository.get_by_email.assert_called_once_with(
        "maria@ejemplo.com"
    )


# ============================================================
# UPDATE
# ============================================================

def test_update_customer(service, db, customer):
    data = CustomerUpdate(
        nombre="María Fernanda"
    )

    service.repository.get_by_id = MagicMock(
        return_value=customer
    )

    service.repository.update = MagicMock(
        return_value=customer
    )

    result = service.update(1, data)

    assert result.id == 1

    service.repository.get_by_id.assert_called_once_with(1)

    service.repository.update.assert_called_once_with(
        customer,
        data,
    )

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(customer)


def test_update_nonexistent_customer(service, db):
    service.repository.get_by_id = MagicMock(
        return_value=None
    )

    data = CustomerUpdate(
        nombre="Nuevo nombre"
    )

    with pytest.raises(CustomerNotFoundError):
        service.update(999, data)

    service.repository.get_by_id.assert_called_once_with(999)

    db.rollback.assert_called_once()
    db.commit.assert_not_called()


# ============================================================
# DEACTIVATE
# ============================================================

def test_deactivate_customer(service, db, customer):
    """Desactiva un cliente activo."""

    service.repository.get_by_id = MagicMock(
        return_value=customer
    )

    def deactivate_customer(obj):
        obj.activo = False
        return obj

    service.repository.deactivate = MagicMock(
        side_effect=deactivate_customer
    )

    result = service.deactivate(1)

    assert result.id == 1
    assert result.activo is False

    service.repository.get_by_id.assert_called_once_with(1)

    service.repository.deactivate.assert_called_once_with(
        customer
    )

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(customer)
    db.rollback.assert_not_called()


def test_deactivate_nonexistent_customer(service, db):
    """No permite desactivar clientes inexistentes."""

    service.repository.get_by_id = MagicMock(
        return_value=None
    )

    service.repository.deactivate = MagicMock()

    with pytest.raises(CustomerNotFoundError):
        service.deactivate(999)

    service.repository.get_by_id.assert_called_once_with(999)
    service.repository.deactivate.assert_not_called()

    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_deactivate_already_inactive_customer(
    service,
    db,
    customer,
):
    """Evita desactivar dos veces al mismo cliente."""

    customer.activo = False

    service.repository.get_by_id = MagicMock(
        return_value=customer
    )

    service.repository.deactivate = MagicMock()

    with pytest.raises(
        CustomerConflictError,
        match="ya se encuentra desactivado",
    ):
        service.deactivate(1)

    service.repository.deactivate.assert_not_called()

    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_deactivate_customer_integrity_error(
    service,
    db,
    customer,
):
    """Revierte la transacción ante errores de integridad."""

    service.repository.get_by_id = MagicMock(
        return_value=customer
    )

    service.repository.deactivate = MagicMock(
        side_effect=IntegrityError(
            "UPDATE clientes",
            {},
            Exception("Integrity constraint"),
        )
    )

    with pytest.raises(
        CustomerConflictError,
        match="restricción de integridad",
    ):
        service.deactivate(1)

    db.rollback.assert_called_once()
    db.commit.assert_not_called()


# ============================================================
# REACTIVATE
# ============================================================

def test_reactivate_customer(service, db, customer):
    """Reactiva un cliente inactivo."""

    customer.activo = False

    service.repository.get_by_id = MagicMock(
        return_value=customer
    )

    def reactivate_customer(obj):
        obj.activo = True
        return obj

    service.repository.reactivate = MagicMock(
        side_effect=reactivate_customer
    )

    result = service.reactivate(1)

    assert result.id == 1
    assert result.activo is True

    service.repository.get_by_id.assert_called_once_with(1)

    service.repository.reactivate.assert_called_once_with(
        customer
    )

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(customer)
    db.rollback.assert_not_called()


def test_reactivate_nonexistent_customer(service, db):
    """No permite reactivar clientes inexistentes."""

    service.repository.get_by_id = MagicMock(
        return_value=None
    )

    service.repository.reactivate = MagicMock()

    with pytest.raises(CustomerNotFoundError):
        service.reactivate(999)

    service.repository.get_by_id.assert_called_once_with(999)
    service.repository.reactivate.assert_not_called()

    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_reactivate_already_active_customer(
    service,
    db,
    customer,
):
    """Evita reactivar clientes que ya están activos."""

    service.repository.get_by_id = MagicMock(
        return_value=customer
    )

    service.repository.reactivate = MagicMock()

    with pytest.raises(
        CustomerConflictError,
        match="ya se encuentra activo",
    ):
        service.reactivate(1)

    service.repository.reactivate.assert_not_called()

    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_reactivate_customer_integrity_error(
    service,
    db,
    customer,
):
    """Revierte la transacción ante errores de integridad."""

    customer.activo = False

    service.repository.get_by_id = MagicMock(
        return_value=customer
    )

    service.repository.reactivate = MagicMock(
        side_effect=IntegrityError(
            "UPDATE clientes",
            {},
            Exception("Integrity constraint"),
        )
    )

    with pytest.raises(
        CustomerConflictError,
        match="restricción de integridad",
    ):
        service.reactivate(1)

    db.rollback.assert_called_once()
    db.commit.assert_not_called()


# ============================================================
# DELETE (COMPATIBILIDAD)
# ============================================================

def test_delete_customer(service, db, customer):
    """delete() delega en la desactivación lógica."""

    service.repository.get_by_id = MagicMock(
        return_value=customer
    )

    def deactivate_customer(obj):
        obj.activo = False
        return obj

    service.repository.deactivate = MagicMock(
        side_effect=deactivate_customer
    )

    service.repository.delete = MagicMock()

    service.delete(1)

    assert customer.activo is False

    service.repository.deactivate.assert_called_once_with(
        customer
    )

    service.repository.delete.assert_not_called()

    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_delete_nonexistent_customer(service, db):
    """delete() también respeta la validación de existencia."""

    service.repository.get_by_id = MagicMock(
        return_value=None
    )

    with pytest.raises(CustomerNotFoundError):
        service.delete(999)

    service.repository.get_by_id.assert_called_once_with(999)

    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_delete_already_inactive_customer(
    service,
    db,
    customer,
):
    """delete() no permite desactivar nuevamente."""

    customer.activo = False

    service.repository.get_by_id = MagicMock(
        return_value=customer
    )

    with pytest.raises(CustomerConflictError):
        service.delete(1)

    db.rollback.assert_called_once()
    db.commit.assert_not_called()
