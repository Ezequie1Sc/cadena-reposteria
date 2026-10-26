
"""Lógica de negocio para la administración de usuarios."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.modules.users.repository import user_repository
from app.modules.users.schemas import (
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.shared.models.role_reference import roles_reference


class UserService:
    """Servicio de operaciones y validaciones de usuarios."""

    @staticmethod
    def _response(user) -> UserResponse:
        """Convierte un usuario al esquema público."""
        return UserResponse.model_validate(user)

    @staticmethod
    def _validate_required_fields(changes: dict) -> None:
        """Impide asignar valores nulos a campos obligatorios."""
        required_fields = {
            "rol_id",
            "nombre",
            "apellido",
            "email",
        }

        if any(
            field in changes and changes[field] is None
            for field in required_fields
        ):
            raise HTTPException(
                status_code=422,
                detail="Los campos obligatorios no pueden ser nulos",
            )

    @staticmethod
    def _validate_role(db: Session, rol_id: int) -> None:
        """Comprueba que el rol exista y esté activo."""

        query = select(
            roles_reference.c.id
        ).where(
            roles_reference.c.id == rol_id
        )

        if db.scalar(query) is None:
            raise HTTPException(
                status_code=422,
                detail="El rol indicado no existe",
            )

        # La referencia SQLAlchemy solo contiene el ID.
        # Consultamos el estado desde la tabla real.
        from sqlalchemy import Boolean, column, table

        roles_table = table(
            "roles",
            column("id"),
            column("activo", Boolean),
        )

        active_query = select(
            roles_table.c.activo
        ).where(
            roles_table.c.id == rol_id
        )

        if db.scalar(active_query) is not True:
            raise HTTPException(
                status_code=422,
                detail="No se puede asignar un rol inactivo",
            )

    @staticmethod
    def _validate_unique_email(
        db: Session,
        email: str,
        exclude_user_id: int | None = None,
    ) -> None:
        """Evita registrar correos electrónicos duplicados."""

        existing = user_repository.get_by_email(
            db,
            email,
        )

        if existing is not None and existing.id != exclude_user_id:
            raise HTTPException(
                status_code=409,
                detail="Ya existe un usuario con este correo electrónico",
            )

    def get_users(
        self,
        db: Session,
        *,
        busqueda: str | None = None,
        rol_id: int | None = None,
        solo_activos: bool | None = True,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """Obtiene usuarios con filtros y paginación."""

        if page < 1:
            raise HTTPException(
                status_code=422,
                detail="La página debe ser mayor o igual a 1",
            )

        if not 1 <= page_size <= 100:
            raise HTTPException(
                status_code=422,
                detail="El tamaño de página debe estar entre 1 y 100",
            )

        if rol_id is not None and rol_id <= 0:
            raise HTTPException(
                status_code=422,
                detail="El identificador del rol debe ser positivo",
            )

        skip = (page - 1) * page_size

        users = user_repository.get_all(
            db=db,
            busqueda=busqueda,
            rol_id=rol_id,
            solo_activos=solo_activos,
            skip=skip,
            limit=page_size,
        )

        total = user_repository.count(
            db=db,
            rol_id=rol_id,
            solo_activos=solo_activos,
        )

        return {
            "items": [
                self._response(user)
                for user in users
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_user_by_id(
        self,
        db: Session,
        user_id: int,
    ) -> UserResponse:
        """Obtiene un usuario por identificador."""

        user = user_repository.get_by_id(db, user_id)

        if user is None:
            raise HTTPException(
                status_code=404,
                detail="Usuario no encontrado",
            )

        return self._response(user)

    def create_user(
        self,
        db: Session,
        data: UserCreate,
    ) -> UserResponse:
        """Registra un usuario con contraseña cifrada."""

        try:
            self._validate_role(db, data.rol_id)
            self._validate_unique_email(db, data.email)

            user = user_repository.create(
                db=db,
                rol_id=data.rol_id,
                nombre=data.nombre,
                apellido=data.apellido,
                email=data.email,
                telefono=data.telefono,
                password_hash=hash_password(data.password),
            )

            db.commit()
            db.refresh(user)

            return self._response(user)

        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="No se pudo registrar el usuario por un conflicto de datos",
            ) from exc

        except Exception:
            db.rollback()
            raise

    def update_user(
        self,
        db: Session,
        user_id: int,
        data: UserUpdate,
    ) -> UserResponse:
        """Actualiza parcialmente los datos de un usuario."""

        try:
            user = user_repository.get_by_id(db, user_id)

            if user is None:
                raise HTTPException(
                    status_code=404,
                    detail="Usuario no encontrado",
                )

            changes = data.model_dump(exclude_unset=True)

            self._validate_required_fields(changes)

            if "rol_id" in changes:
                self._validate_role(db, changes["rol_id"])

            if "email" in changes:
                self._validate_unique_email(
                    db,
                    changes["email"],
                    exclude_user_id=user_id,
                )

            if "password" in changes:
                password = changes.pop("password")

                if password is None:
                    raise HTTPException(
                        status_code=422,
                        detail="La contraseña no puede ser nula",
                    )

                changes["password_hash"] = hash_password(password)

            user = user_repository.update(
                db=db,
                user=user,
                changes=changes,
            )

            db.commit()
            db.refresh(user)

            return self._response(user)

        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="No se pudo actualizar el usuario por un conflicto de datos",
            ) from exc

        except Exception:
            db.rollback()
            raise

    def deactivate_user(
        self,
        db: Session,
        user_id: int,
    ) -> UserResponse:
        """Desactiva un usuario sin eliminarlo físicamente."""

        try:
            user = user_repository.get_by_id(db, user_id)

            if user is None:
                raise HTTPException(
                    status_code=404,
                    detail="Usuario no encontrado",
                )

            if user.activo:
                user = user_repository.deactivate(
                    db,
                    user,
                )

                db.commit()
                db.refresh(user)

            return self._response(user)

        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="No se pudo desactivar el usuario",
            ) from exc

        except Exception:
            db.rollback()
            raise

    def reactivate_user(
        self,
        db: Session,
        user_id: int,
    ) -> UserResponse:
        """Reactiva un usuario si su rol continúa activo."""

        try:
            user = user_repository.get_by_id(db, user_id)

            if user is None:
                raise HTTPException(
                    status_code=404,
                    detail="Usuario no encontrado",
                )

            if not user.activo:
                self._validate_role(db, user.rol_id)

                user = user_repository.reactivate(
                    db,
                    user,
                )

                db.commit()
                db.refresh(user)

            return self._response(user)

        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="No se pudo reactivar el usuario",
            ) from exc

        except Exception:
            db.rollback()
            raise


user_service = UserService()
