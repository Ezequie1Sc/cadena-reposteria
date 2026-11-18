import pytest
from tests.security.conftest import (
    security_db as security_db,
    security_client as security_client,
    headers as headers,
    test_hash as test_hash,
)
from app.modules.payments.model import PaymentMethod


@pytest.fixture(autouse=True)
def methods(security_db):
    for i, name in enumerate(["EFECTIVO", "SPEI", "DEPOSITO", "TARJETA"], 1):
        security_db.add(PaymentMethod(id=i, codigo=name, nombre=name, activo=True))
    security_db.commit()
