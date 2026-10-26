"""Utilidades para crear roles y usuarios de prueba."""

from sqlalchemy.orm import Session

from app.modules.users.model import User
from app.shared.models.role_reference import roles_reference


def create_test_users(db: Session, user_ids: tuple[int, ...]) -> None:
    """Crea un rol y usuarios válidos para las pruebas de empleados."""

    db.execute(
        roles_reference.insert().values(id=1)
    )

    for user_id in user_ids:
        db.add(
            User(
                id=user_id,
                rol_id=1,
                nombre=f"Usuario {user_id}",
                apellido="Prueba",
                email=f"usuario{user_id}@example.com",
                password_hash="hash-ficticio-solo-para-tests",
                activo=True,
            )
        )

    db.flush()