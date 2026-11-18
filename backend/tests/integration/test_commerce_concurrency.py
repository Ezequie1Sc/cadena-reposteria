"""Race checks on actual PostgreSQL, using different sessions and workers."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import datetime, timezone
from decimal import Decimal
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func, text
from app.modules.users.model import User
from app.modules.employees.model import Employee
from app.modules.payments.model import PaymentMethod, Payment
from app.modules.sales.model import Sale
from app.modules.inventory.model import Inventory, InventoryMovement
from app.modules.sales.schemas import SaleCreate
from app.modules.sales.service import create_sale, cancel_sale
from app.modules.payments.schemas import PaymentCreate, PaymentTransition
from app.modules.payments.service import create_payment, transition_payment
from app.shared.commerce import CancelRequest, DateFilters
from app.modules.reports.repository import sales_totals


@pytest.fixture
def commerce_pg(pg_case):
    factory, ids = pg_case
    with factory() as db:
        db.execute(text("INSERT INTO roles(id) VALUES(1),(2)"))
        actors = []
        for i in range(2):
            user = User(
                rol_id=2,
                nombre="Test",
                apellido="Test",
                email=f"race{i}@example.com",
                password_hash="not-a-login-hash",
                activo=True,
            )
            db.add(user)
            db.flush()
            actors.append(user.id)
            db.add(
                Employee(
                    usuario_id=user.id,
                    sucursal_id=ids["branch"],
                    numero_empleado=f"R{i}",
                    puesto="Caja",
                    activo=True,
                )
            )
        admin = User(
            rol_id=1,
            nombre="Admin",
            apellido="Test",
            email="adminrace@example.com",
            password_hash="not-a-login-hash",
            activo=True,
        )
        db.add(admin)
        db.flush()
        ids["admin"] = admin.id
        db.add(PaymentMethod(codigo="EFECTIVO", nombre="Efectivo", activo=True))
        db.commit()
    return factory, ids, actors


def data(ids, qty=2):
    return SaleCreate(
        sucursal_id=ids["branch"],
        productos=[{"producto_id": ids["product"], "cantidad": qty}],
    )


def simultaneous(fn):
    barrier = Barrier(2)

    def run(i):
        barrier.wait(timeout=10)
        try:
            return fn(i)
        except HTTPException as exc:
            return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        return list(pool.map(run, range(2)))


@pytest.mark.parametrize("same_key", [False, True])
def test_sales_race_and_idempotency(commerce_pg, same_key):
    factory, ids, actors = commerce_pg

    def run(i):
        with factory() as db:
            actor = db.get(User, actors[0] if same_key else actors[i])
            return create_sale(
                db, actor, data(ids, 7), "same-key" if same_key else f"race-key-{i}"
            ).id

    results = simultaneous(run)
    if same_key:
        assert results[0] == results[1] and results[0] != 409
    else:
        assert results.count(409) == 1
    with factory() as db:
        assert db.get(Inventory, ids["inventory"]).cantidad == 3
        assert db.scalar(select(func.count()).select_from(Sale)) == 1
        assert db.scalar(select(func.count()).select_from(InventoryMovement)) == 1


def test_payment_registration_race(commerce_pg):
    factory, ids, actors = commerce_pg
    with factory() as db:
        sale = create_sale(db, db.get(User, actors[0]), data(ids), "sale-test-key")

    def run(i):
        with factory() as db:
            return create_payment(
                db,
                db.get(User, actors[i]),
                PaymentCreate(venta_id=sale.id, metodo="EFECTIVO", monto=20),
                f"payment-key-{i}",
            ).id

    results = simultaneous(run)
    assert results.count(409) == 1
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Payment)) == 1


def test_duplicate_confirmation_race(commerce_pg):
    factory, ids, actors = commerce_pg
    with factory() as db:
        actor = db.get(User, actors[0])
        sale = create_sale(db, actor, data(ids), "sale-test-key")
        payment = create_payment(
            db,
            actor,
            PaymentCreate(venta_id=sale.id, metodo="EFECTIVO", monto=20),
            "payment-key",
        )

    def run(i):
        with factory() as db:
            transition_payment(
                db,
                db.get(User, actors[i]),
                payment.id,
                PaymentTransition(estado="APROBADO", motivo="Verificación manual"),
            )
            return 200

    assert sorted(simultaneous(run)) == [200, 409]
    with factory() as db:
        assert db.get(Inventory, ids["inventory"]).cantidad == 8
        assert db.get(Sale, sale.id).estado == "CONFIRMADA"


def test_cancel_confirm_race_is_consistent(commerce_pg):
    factory, ids, actors = commerce_pg
    with factory() as db:
        actor = db.get(User, actors[0])
        sale = create_sale(db, actor, data(ids), "sale-test-key")
        payment = create_payment(
            db,
            actor,
            PaymentCreate(venta_id=sale.id, metodo="EFECTIVO", monto=20),
            "payment-key",
        )

    def run(i):
        with factory() as db:
            if i:
                cancel_sale(
                    db,
                    db.get(User, actors[i]),
                    sale.id,
                    CancelRequest(motivo="Cancelar reserva"),
                )
            else:
                transition_payment(
                    db,
                    db.get(User, actors[i]),
                    payment.id,
                    PaymentTransition(estado="APROBADO", motivo="Verificación manual"),
                )
            return 200

    results = simultaneous(run)
    assert results.count(200) == 1
    with factory() as db:
        sale = db.get(Sale, sale.id)
        payment = db.get(Payment, payment.id)
        if sale.estado == "CANCELADA":
            assert (
                payment.estado == "CANCELADO"
                and db.get(Inventory, ids["inventory"]).cantidad == 10
            )
        else:
            assert (
                sale.estado == "CONFIRMADA"
                and payment.estado == "APROBADO"
                and db.get(Inventory, ids["inventory"]).cantidad == 8
            )


def test_two_cancellations_restore_once(commerce_pg):
    factory, ids, actors = commerce_pg
    with factory() as db:
        sale = create_sale(db, db.get(User, actors[0]), data(ids), "sale-test-key")

    def run(i):
        with factory() as db:
            # Deliberately preload: locks must refresh identity-map state.
            db.get(Sale, sale.id)
            cancel_sale(
                db,
                db.get(User, actors[i]),
                sale.id,
                CancelRequest(motivo="Cancelación simultánea"),
            )
            return 200

    assert sorted(simultaneous(run)) == [200, 409]
    with factory() as db:
        assert db.get(Inventory, ids["inventory"]).cantidad == 10


def test_real_postgres_timezone_grouping(commerce_pg):
    factory, ids, actors = commerce_pg
    with factory() as db:
        actor = db.get(User, actors[0])
        sale = create_sale(db, actor, data(ids), "sale-test-key")
        payment = create_payment(
            db,
            actor,
            PaymentCreate(venta_id=sale.id, metodo="EFECTIVO", monto=20),
            "payment-key",
        )
        transition_payment(
            db,
            actor,
            payment.id,
            PaymentTransition(estado="APROBADO", motivo="Pago verificado"),
        )
        row = db.get(Sale, sale.id)
        row.fecha = datetime(2026, 1, 1, 2, tzinfo=timezone.utc)
        db.commit()
        dates = DateFilters(
            desde=datetime(2025, 12, 30, tzinfo=timezone.utc),
            hasta=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        for group, prefix in [
            ("dia", "2025-12-31"),
            ("mes", "2025-12-01"),
            ("anio", "2025-01-01"),
        ]:
            result = sales_totals(db, dates, None, group, "America/Merida", 100, 0)
            assert result[0]["grupo"].startswith(prefix) and result[0][
                "total"
            ] == Decimal("20")
