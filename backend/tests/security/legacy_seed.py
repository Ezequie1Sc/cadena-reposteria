"""Fixtures extending old HTTP tests with real branch assignments.
Business service mocks and original assertions remain unchanged.
"""

from sqlalchemy import text


def seed_scope_tables(engine, module):
    # These deliberately minimal tables support real authorization queries.
    # Users are subsequently created by the original fixture with ids 1,2,3.
    branch = 20 if module == "inventory" else 2
    with engine.begin() as c:
        c.execute(
            text(
                "CREATE TABLE sucursales (id INTEGER PRIMARY KEY, activo BOOLEAN NOT NULL)"
            )
        )
        c.execute(
            text(
                "CREATE TABLE empleados (id INTEGER PRIMARY KEY, usuario_id INTEGER, sucursal_id INTEGER, activo BOOLEAN NOT NULL)"
            )
        )
        c.execute(text("INSERT INTO sucursales VALUES (:id, true)"), {"id": branch})
        c.execute(
            text("INSERT INTO empleados VALUES (1, 2, :branch, true)"),
            {"branch": branch},
        )
        if module == "inventory":
            c.execute(
                text(
                    "CREATE TABLE inventarios (id INTEGER PRIMARY KEY, sucursal_id INTEGER)"
                )
            )
            c.execute(
                text("INSERT INTO inventarios VALUES (1, :branch)"), {"branch": branch}
            )
        else:
            c.execute(
                text(
                    "CREATE TABLE pedidos (id INTEGER PRIMARY KEY, numero_pedido TEXT, sucursal_id INTEGER)"
                )
            )
            c.execute(
                text("INSERT INTO pedidos VALUES (50, 'PED-TEST-0001', :branch)"),
                {"branch": branch},
            )
