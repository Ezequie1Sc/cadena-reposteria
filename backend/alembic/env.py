
"""
Configuración de Alembic para el backend de Cadena de Repostería.

Utiliza la conexión SQLAlchemy existente y limita las migraciones
a las tablas administradas explícitamente por los modelos ORM.

Las tablas preexistentes de Supabase que aún no tienen modelo
no deben modificarse ni eliminarse automáticamente.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool

from app.db.session import Base, engine

# Importar todos los modelos registrados actualmente.
# Es importante mantener este import cuando se agreguen modelos.
import app.models  # noqa: F401


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# Metadatos de los modelos registrados en SQLAlchemy.
target_metadata = Base.metadata


def include_name(name, type_, parent_names):
    """
    Filtra los objetos durante la reflexión de la base de datos.

    Evita que Alembic genere operaciones para eliminar tablas
    existentes que todavía no están representadas en SQLAlchemy.
    """

    if type_ == "schema":
        return name in (None, "public")

    if type_ == "table":
        schema_name = parent_names.get("schema_name")

        if schema_name not in (None, "public"):
            return False

        return name in target_metadata.tables

    return True


def include_object(object_, name, type_, reflected, compare_to):
    """
    Protección adicional para tablas que existen en Supabase
    pero no están registradas en los modelos SQLAlchemy.
    """

    if type_ == "table" and reflected and compare_to is None:
        return False

    return True


def run_migrations_offline() -> None:
    """
    Genera SQL sin establecer una conexión activa.
    """

    context.configure(
        url=engine.url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_name=include_name,
        include_object=include_object,
        compare_type=True,
        include_schemas=False,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Ejecuta migraciones utilizando la conexión configurada
    en app/db/session.py.
    """

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_name=include_name,
            include_object=include_object,
            compare_type=True,
            include_schemas=False,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
