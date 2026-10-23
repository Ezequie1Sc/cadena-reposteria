
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.user_reference import users_reference
from app.repositories.customer_repository import CustomerRepository
from app.schemas.customer import CustomerCreate, CustomerUpdate


class CustomerNotFoundError(Exception):
    """El cliente solicitado no existe."""


class CustomerConflictError(Exception):
    """La operación entra en conflicto con los datos existentes."""


class CustomerValidationError(Exception):
    """Los datos no cumplen las reglas de negocio."""


class CustomerService:
    """Reglas de negocio del módulo de clientes."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = CustomerRepository(db)

    def _validate_user(
        self,
        user_id: int | None,
        *,
        exclude_customer_id: int | None = None,
    ) -> None:
        """Valida que el usuario exista y no esté asociado a otro cliente."""

        if user_id is None:
            return

        statement = select(users_reference.c.id).where(
            users_reference.c.id == user_id
        )

        existing_user = self.db.scalar(statement)

        if existing_user is None:
            raise CustomerValidationError(
                "El usuario asociado no existe."
            )

        if self.repository.exists_by_user_id(
            user_id,
            exclude_customer_id=exclude_customer_id,
        ):
            raise CustomerConflictError(
                "El usuario ya está asociado a otro cliente."
            )

    def create(self, data: CustomerCreate) -> Customer:
        """Registra un nuevo cliente activo."""

        try:
            self._validate_user(data.usuario_id)

            customer = self.repository.create(data)

            self.db.commit()
            self.db.refresh(customer)

            return customer

        except IntegrityError as exc:
            self.db.rollback()
            raise CustomerConflictError(
                "No se pudo registrar el cliente por una "
                "restricción de integridad."
            ) from exc

        except Exception:
            self.db.rollback()
            raise

    def get_by_id(self, customer_id: int) -> Customer:
        """Obtiene un cliente, independientemente de su estado."""

        customer = self.repository.get_by_id(customer_id)

        if customer is None:
            raise CustomerNotFoundError(
                "El cliente solicitado no existe."
            )

        return customer

    def get_all(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        solo_activos: bool | None = None,
    ) -> dict:
        """
        Obtiene un listado paginado de clientes.

        solo_activos:
            True  -> clientes activos.
            False -> clientes inactivos.
            None  -> todos los clientes.
        """

        if page < 1:
            raise CustomerValidationError(
                "La página debe ser mayor o igual a 1."
            )

        if not 1 <= page_size <= 100:
            raise CustomerValidationError(
                "El tamaño de página debe estar entre 1 y 100."
            )

        skip = (page - 1) * page_size

        customers = self.repository.get_all(
            skip=skip,
            limit=page_size,
            solo_activos=solo_activos,
        )

        total = self.repository.count(
            solo_activos=solo_activos,
        )

        return {
            "items": customers,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_by_email(self, email: str) -> list[Customer]:
        """Busca clientes por correo electrónico."""

        return self.repository.get_by_email(
            email.strip()
        )

    def update(
        self,
        customer_id: int,
        data: CustomerUpdate,
    ) -> Customer:
        """Actualiza parcialmente los datos de un cliente."""

        try:
            customer = self.get_by_id(customer_id)

            changes = data.model_dump(
                exclude_unset=True
            )

            if "usuario_id" in changes:
                self._validate_user(
                    changes["usuario_id"],
                    exclude_customer_id=customer_id,
                )

            customer = self.repository.update(
                customer,
                data,
            )

            self.db.commit()
            self.db.refresh(customer)

            return customer

        except IntegrityError as exc:
            self.db.rollback()
            raise CustomerConflictError(
                "No se pudo actualizar el cliente por una "
                "restricción de integridad."
            ) from exc

        except Exception:
            self.db.rollback()
            raise

    def deactivate(self, customer_id: int) -> Customer:
        """
        Desactiva un cliente sin eliminar su registro.

        Conserva su historial de pedidos, ventas y facturas.
        """

        try:
            customer = self.get_by_id(customer_id)

            if not customer.activo:
                raise CustomerConflictError(
                    "El cliente ya se encuentra desactivado."
                )

            customer = self.repository.deactivate(
                customer
            )

            self.db.commit()
            self.db.refresh(customer)

            return customer

        except IntegrityError as exc:
            self.db.rollback()
            raise CustomerConflictError(
                "No se pudo desactivar el cliente por una "
                "restricción de integridad."
            ) from exc

        except Exception:
            self.db.rollback()
            raise

    def reactivate(self, customer_id: int) -> Customer:
        """Reactiva un cliente previamente desactivado."""

        try:
            customer = self.get_by_id(customer_id)

            if customer.activo:
                raise CustomerConflictError(
                    "El cliente ya se encuentra activo."
                )

            customer = self.repository.reactivate(
                customer
            )

            self.db.commit()
            self.db.refresh(customer)

            return customer

        except IntegrityError as exc:
            self.db.rollback()
            raise CustomerConflictError(
                "No se pudo reactivar el cliente por una "
                "restricción de integridad."
            ) from exc

        except Exception:
            self.db.rollback()
            raise

    def delete(self, customer_id: int) -> None:
        """
        Alias de compatibilidad para eliminación lógica.

        Nunca elimina físicamente el cliente.
        """

        self.deactivate(customer_id)
