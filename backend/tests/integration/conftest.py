"""PostgreSQL integration fixtures restricted to a disposable local database."""

import os
from uuid import uuid4
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from app.db.session import Base
import app.db.models
from app.modules.branches.model import Branch
from app.modules.categories.model import Category
from app.modules.customers.model import Customer
from app.modules.products.model import Product
from app.modules.inventory.model import Inventory


@pytest.fixture
def pg_case():
    if os.getenv("RUN_POSTGRES_INTEGRATION_TESTS") != "1":
        pytest.skip("Requires isolated PostgreSQL integration opt-in")
    raw = os.getenv("TEST_DATABASE_URL")
    if not raw:
        pytest.skip("Requires local TEST_DATABASE_URL")
    url = make_url(raw)
    if (
        url.get_backend_name() != "postgresql"
        or url.host not in {"127.0.0.1", "localhost", "::1"}
        or url.database != "reposteria_audit_test"
    ):
        pytest.fail("Integration tests only allow local reposteria_audit_test")
    schema = "audit_" + uuid4().hex
    owner = create_engine(url, hide_parameters=True)
    with owner.begin() as c:
        c.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(
        url, hide_parameters=True, connect_args={"options": f"-csearch_path={schema}"}
    )
    try:
        Base.metadata.create_all(engine)
        factory = sessionmaker(engine, expire_on_commit=False, autoflush=False)
        with factory() as db:
            category = Category(nombre="Test", activo=True)
            branch = Branch(
                nombre="Test",
                codigo="T",
                direccion="Test",
                ciudad="Test",
                estado="Test",
                activo=True,
            )
            customer = Customer(nombre="Test", activo=True)
            db.add_all([category, branch, customer])
            db.flush()
            product = Product(
                categoria_id=category.id, nombre="Test", sku="T", precio=10, activo=True
            )
            db.add(product)
            db.flush()
            inventory = Inventory(
                producto_id=product.id,
                sucursal_id=branch.id,
                cantidad=10,
                stock_minimo=1,
            )
            db.add(inventory)
            db.commit()
            ids = {
                "inventory": inventory.id,
                "product": product.id,
                "branch": branch.id,
                "customer": customer.id,
            }
        yield factory, ids
    finally:
        engine.dispose()
        with owner.begin() as c:
            c.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        owner.dispose()
