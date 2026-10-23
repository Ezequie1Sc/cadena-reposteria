
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.db.session import engine


def main():
    try:
        print("Conectando a PostgreSQL...")

        with engine.connect() as connection:
            database = connection.execute(
                text("SELECT current_database()")
            ).scalar_one()

            products = connection.execute(
                text("SELECT COUNT(*) FROM public.productos")
            ).scalar_one()

            print("Conexion PostgreSQL exitosa")
            print(f"Base de datos: {database}")
            print(f"Productos registrados: {products}")

    except OperationalError as error:
        print("Error de conexion PostgreSQL")

        original_error = error.orig
        sqlstate = getattr(original_error, "sqlstate", None)

        if sqlstate:
            print(f"Codigo SQLSTATE: {sqlstate}")

        message = str(original_error).lower()

        if "password authentication failed" in message:
            print("Posible causa: usuario o contraseña incorrectos.")
        elif "could not translate host name" in message:
            print("Posible causa: nombre del servidor incorrecto.")
        elif "name or service not known" in message:
            print("Posible causa: error de DNS.")
        elif "connection refused" in message:
            print("Posible causa: servidor o puerto no disponible.")
        elif "timeout" in message or "timed out" in message:
            print("Posible causa: tiempo de espera agotado.")
        elif "network is unreachable" in message:
            print("Posible causa: problema de conectividad de red.")
        else:
            print("Causa no identificada. Revisa la configuracion.")

    except SQLAlchemyError as error:
        print(f"Error SQLAlchemy: {type(error).__name__}")


if __name__ == "__main__":
    main()
