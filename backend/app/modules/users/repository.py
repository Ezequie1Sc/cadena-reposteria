
"""Repositorio de acceso a datos para usuarios."""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.users.model import User


class UserRepository:
    """Operaciones de persistencia para usuarios."""

    def get_all(
        self,
        db: Session,
        *,
        busqueda: str | None = None,
        rol_id: int | None = None,
        solo_activos: bool | None = True,
        skip: int = 0,
        limit: int = 20,
    ) -> list[User]:
        """Lista usuarios con filtros y paginación."""

        query = select(User)

        if solo_activos is not None:
            query = query.where(
                User.activo.is_(solo_activos)
            )

        if rol_id is not None:
            query = query.where(
                User.rol_id == rol_id
            )

        if busqueda:
            termino = busqueda.strip()

            if termino:
                query = query.where(
                    or_(
                        User.nombre.ilike(f"%{termino}%"),
                        User.apellido.ilike(f"%{termino}%"),
                        User.email.ilike(f"%{termino}%"),
                    )
                )

        query = (
            query
            .order_by(User.id)
            .offset(skip)
            .limit(limit)
        )

        return list(db.scalars(query).all())

    def count(
        self,
        db: Session,
        *,
        busqueda: str | None = None,
        rol_id: int | None = None,
        solo_activos: bool | None = True,
    ) -> int:
        """Cuenta usuarios aplicando los mismos filtros del listado."""

        query = (
            select(func.count())
            .select_from(User)
        )

        if solo_activos is not None:
            query = query.where(
                User.activo.is_(solo_activos)
            )

        if rol_id is not None:
            query = query.where(
                User.rol_id == rol_id
            )

        if busqueda:
            termino = busqueda.strip()

            if termino:
                query = query.where(
                    or_(
                        User.nombre.ilike(f"%{termino}%"),
                        User.apellido.ilike(f"%{termino}%"),
                        User.email.ilike(f"%{termino}%"),
                    )
                )

        return db.scalar(query) or 0

    def get_by_id(
        self,
        db: Session,
        user_id: int,
    ) -> User | None:
        """Obtiene un usuario por identificador."""

        return db.get(User, user_id)

    def get_by_email(
        self,
        db: Session,
        email: str,
    ) -> User | None:
        """Busca un usuario por correo sin distinguir mayúsculas."""

        normalized_email = email.strip().lower()

        query = select(User).where(
            func.lower(User.email) == normalized_email
        )

        return db.scalar(query)

    def create(
        self,
        db: Session,
        *,
        rol_id: int,
        nombre: str,
        apellido: str,
        email: str,
        password_hash: str,
        telefono: str | None = None,
    ) -> User:
        """Registra un usuario con su contraseña previamente cifrada."""

        user = User(
            rol_id=rol_id,
            nombre=nombre,
            apellido=apellido,
            email=email,
            password_hash=password_hash,
            telefono=telefono,
            activo=True,
        )

        db.add(user)
        db.flush()
        db.refresh(user)

        return user

    def update(
        self,
        db: Session,
        user: User,
        *,
        changes: dict,
    ) -> User:
        """Actualiza únicamente los campos permitidos."""

        allowed_fields = {
            "rol_id",
            "nombre",
            "apellido",
            "email",
            "telefono",
            "password_hash",
        }

        invalid_fields = set(changes) - allowed_fields

        if invalid_fields:
            raise ValueError(
                "No se permite modificar los campos: "
                + ", ".join(sorted(invalid_fields))
            )

        for field, value in changes.items():
            setattr(user, field, value)

        if changes:
            db.flush()
            db.refresh(user)

        return user

    def deactivate(
        self,
        db: Session,
        user: User,
    ) -> User:
        """Desactiva un usuario sin eliminar su registro."""

        user.activo = False

        db.flush()
        db.refresh(user)

        return user

    def reactivate(
        self,
        db: Session,
        user: User,
    ) -> User:
        """Reactiva un usuario previamente desactivado."""

        user.activo = True

        db.flush()
        db.refresh(user)

        return user


user_repository = UserRepository()
