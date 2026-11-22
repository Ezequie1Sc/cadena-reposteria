
"""Inicialización controlada del primer administrador."""

from getpass import getpass

from sqlalchemy import func, select

from app.core.roles import RoleID, catalog_role_active
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.modules.users.model import User
from app.modules.users.repository import user_repository
from app.shared.models.role_reference import roles_reference
ADMIN_ROLE_ID = RoleID.ADMINISTRADOR


def main() -> None:
    print("\n=== INICIALIZACIÓN DEL PRIMER ADMINISTRADOR ===")
    print("ATENCIÓN: este proceso escribirá en la base de datos configurada.")
    print("No lo ejecutes si no estás autorizado a administrar esa base.\n")

    nombre = input("Nombre: ").strip()
    apellido = input("Apellido: ").strip()
    email = input("Correo: ").strip().lower()

    if not nombre or not apellido or not email or "@" not in email:
        raise SystemExit("Nombre, apellido o correo no válido.")

    password = getpass("Contraseña: ")
    confirmation = getpass("Confirmar contraseña: ")

    if password != confirmation:
        raise SystemExit("Las contraseñas no coinciden.")

    if len(password) < 12:
        raise SystemExit("Utiliza una contraseña de al menos 12 caracteres.")

    print(f"\nSe creará una cuenta con rol Administrador (ID {ADMIN_ROLE_ID.value}).")
    print(f"Correo: {email}")
    print("Base de datos: la configurada actualmente en el backend.")

    confirmation_text = input(
        "\nEscribe CREAR ADMIN para confirmar: "
    ).strip()

    if confirmation_text != "CREAR ADMIN":
        print("Operación cancelada.")
        return

    db = SessionLocal()

    try:
        # Serializar dos inicializaciones en la fila del rol antes de contar cuentas.
        db.scalar(select(roles_reference.c.id).where(
            roles_reference.c.id == ADMIN_ROLE_ID
        ).with_for_update())
        if catalog_role_active(db, ADMIN_ROLE_ID) is not True:
            raise SystemExit("El rol Administrador no está disponible.")

        # Evitar inicializar otro administrador.
        existing_admin = db.scalar(
            select(User.id)
            .where(User.rol_id == ADMIN_ROLE_ID)
            .limit(1)
        )

        if existing_admin is not None:
            raise SystemExit(
                "Ya existe un administrador. "
                "No se creará otra cuenta."
            )

        # Comprobar que el correo no esté registrado.
        existing_email = db.scalar(
            select(User.id)
            .where(func.lower(User.email) == email)
            .limit(1)
        )

        if existing_email is not None:
            raise SystemExit(
                "El correo ya pertenece a otro usuario."
            )

        admin = user_repository.create(
            db=db,
            rol_id=ADMIN_ROLE_ID,
            nombre=nombre,
            apellido=apellido,
            email=email,
            password_hash=hash_password(password),
        )

        db.commit()

        print("\nAdministrador creado correctamente.")
        print(f"ID: {admin.id}")
        print(f"Correo: {admin.email}")
        print("Rol: Administrador")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
