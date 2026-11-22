import os
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

import app.db.models  # noqa
from app.api.routes.auth import router as auth
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.core.jwt import create_access_token
from app.db.session import Base, get_db
from app.modules.administracion import catalog, company, images, imports, onboarding
from app.modules.administracion.upload_limit import UploadLimit
from app.modules.employees.routes import router as employees
from app.modules.inventory.routes import router as inventory
from app.modules.products.routes import router as products
from app.modules.users.routes import router as users


@pytest.fixture(scope="module")
def factory():
    url = os.getenv("TEST_DATABASE_URL")
    if os.getenv("RUN_POSTGRES_INTEGRATION_TESTS") != "1" or not url:
        pytest.skip("Requiere PostgreSQL local desechable")
    base = make_url(url)
    assert (
        base.host in ("localhost", "127.0.0.1", "::1")
        and base.database == "reposteria_audit_test"
    )
    dbname = "dg_prueba_" + uuid4().hex
    control = create_engine(base, isolation_level="AUTOCOMMIT")
    with control.connect() as c:
        c.exec_driver_sql(f"CREATE DATABASE {dbname}")
    engine = create_engine(base.set(database=dbname))
    try:
        Base.metadata.create_all(engine)
        with engine.begin() as c:
            # Proyección local del esquema previo. Aplicar la revisión real en la BD efímera.
            c.exec_driver_sql(
                "ALTER TABLE movimientos_inventario DROP COLUMN cantidad_anterior, DROP COLUMN cantidad_nueva"
            )
        import subprocess
        import sys

        migration_env = {
            **os.environ,
            "MIGRATION_DATABASE_URL": engine.url.render_as_string(hide_password=False),
        }
        for args in (["stamp", "b27a913c6d02"], ["upgrade", "d209ec761501"]):
            subprocess.run(
                [sys.executable, "-m", "alembic", *args], check=True, env=migration_env
            )
        with engine.begin() as c:
            assert (
                c.exec_driver_sql(
                    "SELECT version_num FROM alembic_version"
                ).scalar_one()
                == "d209ec761501"
            )
            c.exec_driver_sql(
                "ALTER TABLE roles ADD COLUMN activo boolean DEFAULT true"
            )
            c.exec_driver_sql("ALTER TABLE roles ADD COLUMN nombre text")
            c.exec_driver_sql(
                "INSERT INTO roles(id,nombre) VALUES(1,'Administrador'),(2,'Empleado'),(3,'Cliente')"
            )
            c.exec_driver_sql("""INSERT INTO usuarios(rol_id,nombre,apellido,email,password_hash)
                              VALUES (1,'Test','Admin','admin@example.org','!'),(2,'Test','Staff','staff@example.org','!'),
                              (3,'Test','Cliente','cliente@example.org','!')""")
            c.exec_driver_sql("""INSERT INTO sucursales(nombre,codigo,direccion,ciudad,estado)
                              VALUES('Centro','C','x','x','x'),('Norte','N','x','x','x')""")
            c.exec_driver_sql("INSERT INTO categorias(nombre) VALUES('Pan')")
            c.exec_driver_sql(
                "INSERT INTO empleados(usuario_id,sucursal_id,puesto,numero_empleado) VALUES(2,1,'Caja','HIST-1')"
            )
        yield sessionmaker(engine)
    finally:
        engine.dispose()
        with control.connect() as c:
            c.exec_driver_sql(f"DROP DATABASE {dbname}")
        control.dispose()


@pytest.fixture
def api(factory, monkeypatch):
    monkeypatch.setattr(settings, "administracion_habilitada", True)
    monkeypatch.setattr(
        settings, "correo_clave_cifrado", Fernet.generate_key().decode()
    )
    monkeypatch.setattr(settings, "portal_url", "https://portal.example.org")
    app = FastAPI()
    register_error_handlers(app)
    app.add_middleware(UploadLimit)
    for r in (
        catalog.router,
        company.router,
        images.router,
        imports.router,
        onboarding.router,
        users,
        employees,
        products,
        inventory,
        auth,
    ):
        app.include_router(r)

    def session():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = session
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client


def headers(uid=1, key=None):
    h = {"Authorization": "Bearer " + create_access_token(uid)}
    if key:
        h["Idempotency-Key"] = key
    return h
