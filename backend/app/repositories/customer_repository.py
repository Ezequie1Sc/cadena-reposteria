
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.schemas.customer import CustomerCreate, CustomerUpdate


class CustomerRepository:
    """Operaciones de persistencia para clientes."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: CustomerCreate) -> Customer:
        """Registra un cliente activo en la sesión actual."""

        customer = Customer(
            **data.model_dump(),
            activo=True,
        )

        self.db.add(customer)
        self.db.flush()
        self.db.refresh(customer)

        return customer

    def get_by_id(self, customer_id: int) -> Customer | None:
        """Obtiene un cliente por su identificador."""

        statement = select(Customer).where(
            Customer.id == customer_id
        )

        return self.db.scalar(statement)

    def get_by_user_id(self, user_id: int) -> Customer | None:
        """Busca el cliente asociado a un usuario."""

        statement = select(Customer).where(
            Customer.usuario_id == user_id
        )

        return self.db.scalar(statement)

    def get_by_email(self, email: str) -> list[Customer]:
        """
        Busca clientes por correo electrónico.

        El email no tiene una restricción UNIQUE en PostgreSQL,
        por lo que puede devolver varios registros.
        """

        statement = (
            select(Customer)
            .where(
                func.lower(Customer.email) == email.lower()
            )
            .order_by(Customer.id)
        )

        return list(self.db.scalars(statement).all())

    def get_all(
        self,
        *,
        skip: int = 0,
        limit: int = 20,
        solo_activos: bool | None = None,
    ) -> list[Customer]:
        """
        Obtiene clientes con paginación.

        solo_activos:
            True  -> únicamente clientes activos.
            False -> únicamente clientes inactivos.
            None  -> todos los clientes.
        """

        statement = select(Customer)

        if solo_activos is not None:
            statement = statement.where(
                Customer.activo.is_(solo_activos)
            )

        statement = (
            statement
            .order_by(Customer.id)
            .offset(skip)
            .limit(limit)
        )

        return list(self.db.scalars(statement).all())

    def count(
        self,
        *,
        solo_activos: bool | None = None,
    ) -> int:
        """Cuenta clientes aplicando el filtro de estado."""

        statement = (
            select(func.count())
            .select_from(Customer)
        )

        if solo_activos is not None:
            statement = statement.where(
                Customer.activo.is_(solo_activos)
            )

        return self.db.scalar(statement) or 0

    def update(
        self,
        customer: Customer,
        data: CustomerUpdate,
    ) -> Customer:
        """Actualiza únicamente los campos proporcionados."""

        changes: dict[str, Any] = data.model_dump(
            exclude_unset=True
        )

        for field, value in changes.items():
            setattr(customer, field, value)

        self.db.flush()
        self.db.refresh(customer)

        return customer

    def deactivate(self, customer: Customer) -> Customer:
        """
        Desactiva un cliente sin eliminarlo físicamente.

        Conserva sus relaciones con pedidos, ventas y facturas.
        """

        customer.activo = False

        self.db.flush()
        self.db.refresh(customer)

        return customer

    def reactivate(self, customer: Customer) -> Customer:
        """Reactiva un cliente previamente desactivado."""

        customer.activo = True

        self.db.flush()
        self.db.refresh(customer)

        return customer

    def delete(self, customer: Customer) -> None:
        """
        Mantiene compatibilidad con el servicio existente.

        Realiza una desactivación lógica en lugar de
        eliminar físicamente el registro.
        """

        self.deactivate(customer)

    def exists_by_user_id(
        self,
        user_id: int,
        *,
        exclude_customer_id: int | None = None,
    ) -> bool:
        """
        Comprueba si un usuario ya está asociado a un cliente.

        Permite excluir el cliente actual durante una actualización.
        """

        statement = select(Customer.id).where(
            Customer.usuario_id == user_id
        )

        if exclude_customer_id is not None:
            statement = statement.where(
                Customer.id != exclude_customer_id
            )

        return self.db.scalar(statement) is not None
