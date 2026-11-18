
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Cargar las variables del .env del backend
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    sys.exit("ERROR: No se encontró DATABASE_URL en el archivo .env")

try:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"connect_timeout": 10},
        pool_pre_ping=True,
    )

    with engine.connect() as connection:
        result = connection.execute(
            text("""
                SELECT
                    current_user AS usuario_actual,
                    session_user AS usuario_sesion,
                    current_setting('row_security') AS rls_config,
                    r.rolbypassrls AS puede_omitir_rls,
                    r.rolsuper AS superusuario
                FROM pg_roles r
                WHERE r.rolname = current_user
            """)
        )

        data = result.mappings().one()

        print("\n=== DIAGNÓSTICO DE SEGURIDAD ===")
        print(f"Usuario actual: {data['usuario_actual']}")
        print(f"Usuario de sesión: {data['usuario_sesion']}")
        print(f"RLS configurado: {data['rls_config']}")
        print(f"Puede omitir RLS: {data['puede_omitir_rls']}")
        print(f"Superusuario: {data['superusuario']}")
        owned = connection.execute(text("""
            SELECT count(*) FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
              AND pg_get_userbyid(c.relowner) = current_user
              AND c.relrowsecurity AND NOT c.relforcerowsecurity
        """)).scalar_one()
        print(f"Tablas propias con RLS no forzado: {owned}")
        print("RLS=on no demuestra aislamiento por usuario de la API.")
        print("================================\n")

except Exception as error:
    print(f"Error al conectar o consultar PostgreSQL: {type(error).__name__}")
    sys.exit(1)

finally:
    if "engine" in locals():
        engine.dispose()
