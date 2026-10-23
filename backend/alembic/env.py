
"""
Configuración de Alembic para el backend de Cadena de Repostería.

Utiliza la conexión SQLAlchemy existente y limita las migraciones
a las tablas administradas explícitamente por los modelos ORM.

Las tablas preexistentes de Supabase que aún no tienen un modelo
completo no deben modificarse ni eliminarse automáticamente.

Las tablas marcadas como reference_only se utilizan únicamente
para resolver relaciones y claves foráneas.
"""

from logging.config import fileConfig

from alembic import context

from app.db.session import Base, engine

# Registrar los modelos ORM y las tablas de referencia.
import app.db.models  # noqa: F401


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


target_metadata = Base.metadata


def include_name(name, type_, parent_names):
    """
    Filtra los objetos durante la reflexión de PostgreSQL.

    Protege las tablas existentes que todavía no están
    administradas completamente mediante modelos ORM.
    """

    if type_ == "schema":
        return name in (None, "public")

    if type_ == "table":
        schema_name = parent_names.get("schema_name")

        if schema_name not in (None, "public"):
            return False

        # Excluir tablas utilizadas únicamente como referencia.
        table_key = name

        table = target_metadata.tables.get(table_key)

        if table is not None and table.info.get("reference_only"):
            return False

        # Administrar únicamente las tablas registradas.
        return table_key in target_metadata.tables

    return True


def include_object(object_, name, type_, reflected, compare_to):
    """
    Protección adicional durante la comparación de esquemas.

    Excluye las tablas de referencia y evita operaciones
    de eliminación sobre tablas no administradas.
    """

    if type_ == "table":
        if object_.info.get("reference_only"):
            return False

        if compare_to is not None:
            if compare_to.info.get("reference_only"):
                return False

        if reflected and compare_to is None:
            return False

    return True


def run_migrations_offline() -> None:
    """
    Genera SQL de migraciones sin establecer una conexión activa.
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
    Ejecuta migraciones utilizando la conexión SQLAlchemy
    configurada en app/db/session.py.
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
