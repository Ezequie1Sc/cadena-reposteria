
"""Lógica de negocio para el registro público de clientes."""

from fastapi import HTTPException, status
from sqlalchemy import Boolean, column, select, table
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.modules.auth.registration_schemas import (
    CustomerRegistrationRequest,
    CustomerRegistrationResponse,
)
from app.modules.users.repository import user_repository


CUSTOMER_ROLE_ID = 3

roles_table = table(
    "roles",
    column("id"),
    column("activo", Boolean),
)


class CustomerRegistrationService:
    """Gestiona el registro público de cuentas de clientes."""

    @staticmethod
    def _validate_customer_role(db: Session) -> None:
        """Comprueba que el rol Cliente exista y esté activo."""

        role_active = db.scalar(
            select(roles_table.c.activo).where(
                roles_table.c.id == CUSTOMER_ROLE_ID
            )
        )

        if role_active is not True:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="El registro de clientes no está disponible",
            )

    @staticmethod
    def _validate_unique_email(
        db: Session,
        email: str,
    ) -> None:
        """Impide registrar un correo utilizado por otra cuenta."""

        existing_user = user_repository.get_by_email(
            db,
            email,
        )

        if existing_user is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un usuario con este correo electrónico",
            )

    def register_customer(
        self,
        db: Session,
        data: CustomerRegistrationRequest,
    ) -> CustomerRegistrationResponse:
        """Registra un usuario con el rol Cliente."""

        try:
            self._validate_customer_role(db)

            normalized_email = str(data.email).strip().lower()

            self._validate_unique_email(
                db,
                normalized_email,
            )

            password_hash = hash_password(
                data.password
            )

            user = user_repository.create(
                db=db,
                rol_id=CUSTOMER_ROLE_ID,
                nombre=data.nombre,
                apellido=data.apellido,
                email=normalized_email,
                telefono=data.telefono,
                password_hash=password_hash,
            )

            db.commit()
            db.refresh(user)

            return CustomerRegistrationResponse.model_validate(
                user
            )

        except IntegrityError as exc:
            db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No se pudo registrar el usuario por un conflicto de datos",
            ) from exc

        except Exception:
            db.rollback()
            raise


customer_registration_service = CustomerRegistrationService()
