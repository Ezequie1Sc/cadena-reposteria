
"""Pruebas de concurrencia del rate limiting en PostgreSQL."""

import os

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from sqlalchemy import delete, select

from app.db.session import SessionLocal, engine
from app.modules.auth.rate_limit_model import AuthRateLimit
from app.modules.auth.rate_limit_repository import (
    rate_limit_repository,
)


@pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_INTEGRATION_TESTS") != "1",
    reason="Requiere RUN_POSTGRES_INTEGRATION_TESTS=1",
)
def test_concurrent_attempts_are_counted_atomically():
    """Verifica que PostgreSQL no pierde incrementos concurrentes."""

    if engine.dialect.name != "postgresql":
        pytest.skip("Esta prueba requiere PostgreSQL")

    key = f"test:concurrency:{uuid4().hex}"

    total_attempts = 12
    limit = 5
    window_seconds = 60

    def record_attempt():
        """Registra un intento utilizando una sesión independiente."""

        with SessionLocal() as db:
            return rate_limit_repository.record_attempt(
                db,
                key=key,
                limit=limit,
                window_seconds=window_seconds,
            )

    try:
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(
                executor.map(
                    lambda _: record_attempt(),
                    range(total_attempts),
                )
            )

        attempts = sorted(
            result.attempts
            for result in results
        )

        assert attempts == list(
            range(1, total_attempts + 1)
        )

        allowed_results = [
            result
            for result in results
            if result.allowed
        ]

        blocked_results = [
            result
            for result in results
            if not result.allowed
        ]

        assert len(allowed_results) == 5
        assert len(blocked_results) == 7

        assert all(
            result.retry_after > 0
            for result in blocked_results
        )

        with SessionLocal() as db:
            stored_record = db.scalar(
                select(AuthRateLimit).where(
                    AuthRateLimit.key == key
                )
            )

            assert stored_record is not None
            assert stored_record.attempts == total_attempts

    finally:
        with SessionLocal() as db:
            db.execute(
                delete(AuthRateLimit).where(
                    AuthRateLimit.key == key
                )
            )
            db.commit()
