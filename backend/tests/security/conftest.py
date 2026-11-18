"""Real JWT and ORM with a fresh, isolated database for each test."""

from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.db.session import Base, get_db
import app.db.models as registered_models
from app.api.routes.auth import get_rate_limit_session_factory
from app.core.security import hash_password
from app.core.jwt import create_access_token
from app.modules.users.model import User
from app.modules.branches.model import Branch
from app.modules.categories.model import Category
from app.modules.products.model import Product
from app.modules.customers.model import Customer
from app.modules.employees.model import Employee
from app.modules.inventory.model import Inventory
from app.modules.orders.model import Order


@pytest.fixture(scope="session")
def test_hash():
    return hash_password("AuditPassword2026!")


@pytest.fixture
def security_db(test_hash):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def enable_fk(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(
            text("ALTER TABLE roles ADD COLUMN activo BOOLEAN NOT NULL DEFAULT true")
        )
        c.execute(text("ALTER TABLE roles ADD COLUMN nombre TEXT"))
        c.execute(text("ALTER TABLE roles ADD COLUMN descripcion TEXT"))
        c.execute(
            text(
                "INSERT INTO roles(id,nombre,activo) VALUES (1,'Administrador',true),(2,'Empleado',true),(3,'Cliente',true),(4,'Desconocido',true)"
            )
        )
    factory = sessionmaker(engine, expire_on_commit=False, autoflush=False)
    with factory() as db:
        for uid, role in [(1, 1), (2, 2), (3, 3), (4, 3), (5, 2), (6, 4)]:
            db.add(
                User(
                    id=uid,
                    rol_id=role,
                    nombre="Prueba",
                    apellido="Auditoría",
                    email=f"user{uid}@example.com",
                    password_hash=test_hash,
                    activo=True,
                )
            )
        for bid in [1, 2]:
            db.add(
                Branch(
                    id=bid,
                    nombre=f"Sucursal {bid}",
                    codigo=f"S{bid}",
                    direccion="Calle 1",
                    ciudad="Campeche",
                    estado="Campeche",
                    activo=True,
                )
            )
        db.add(Category(id=1, nombre="Pasteles", activo=True))
        db.flush()
        db.add(
            Product(
                id=1,
                categoria_id=1,
                nombre="Pastel",
                sku="TEST-1",
                precio=Decimal("30.00"),
                activo=True,
            )
        )
        db.flush()
        for uid, bid in [(2, 1), (5, 2)]:
            db.add(
                Employee(
                    usuario_id=uid,
                    sucursal_id=bid,
                    numero_empleado=f"E{uid}",
                    puesto="Encargado",
                    activo=True,
                )
            )
        for cid, uid in [(10, 3), (11, 4)]:
            db.add(
                Customer(
                    id=cid,
                    usuario_id=uid,
                    nombre="Cliente",
                    apellido="Prueba",
                    email=f"user{uid}@example.com",
                    activo=True,
                )
            )
        db.flush()
        for bid, cid in [(1, 10), (2, 11)]:
            db.add(
                Inventory(
                    id=bid, producto_id=1, sucursal_id=bid, cantidad=20, stock_minimo=2
                )
            )
            db.add(
                Order(
                    id=20 + bid,
                    numero_pedido=f"PED-{bid}",
                    cliente_id=cid,
                    sucursal_id=bid,
                    estado="PENDIENTE",
                    subtotal=Decimal("0"),
                    total=Decimal("0"),
                )
            )
        db.commit()
        yield db
    engine.dispose()


@pytest.fixture
def security_client(security_db):
    factory = sessionmaker(security_db.get_bind(), expire_on_commit=False)

    def database():
        try:
            yield security_db
        finally:
            security_db.rollback()

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_rate_limit_session_factory] = lambda: factory
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def headers():
    return lambda uid: {"Authorization": f"Bearer {create_access_token(uid)}"}
