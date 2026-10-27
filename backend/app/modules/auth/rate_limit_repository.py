
"""Persistencia de contadores para limitar solicitudes de autenticación."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.modules.auth.rate_limit_model import AuthRateLimit


@dataclass(frozen=True)
class RateLimitResult:
    """Resultado de contabilizar una solicitud."""

    allowed: bool
    attempts: int
    retry_after: int


class RateLimitRepository:
    """Gestiona contadores compartidos de solicitudes."""

    def record_attempt(
        self,
        db: Session,
        *,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitResult:
        """
        Registra una solicitud y comprueba su límite.

        PostgreSQL utiliza un UPSERT atómico. SQLite dispone de
        una implementación para pruebas funcionales.
        """
        if not key or len(key) > 128:
            raise ValueError("La clave debe tener entre 1 y 128 caracteres")

        if limit < 1:
            raise ValueError("El límite debe ser mayor que cero")

        if window_seconds < 1:
            raise ValueError("La ventana debe ser mayor que cero")

        dialect = db.get_bind().dialect.name

        if dialect == "postgresql":
            return self._record_postgresql(
                db,
                key=key,
                limit=limit,
                window_seconds=window_seconds,
            )

        if dialect == "sqlite":
            return self._record_sqlite(
                db,
                key=key,
                limit=limit,
                window_seconds=window_seconds,
            )

        raise NotImplementedError(
            f"Motor de base de datos no compatible: {dialect}"
        )

    def _record_postgresql(
        self,
        db: Session,
        *,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitResult:
        """Incrementa el contador mediante un UPSERT atómico."""

        table = AuthRateLimit.__table__

        now = func.now()
        expires_at = now + func.make_interval(
            0, 0, 0, 0, 0, 0, window_seconds
        )

        statement = pg_insert(table).values(
            key=key,
            attempts=1,
            window_started_at=now,
            expires_at=expires_at,
        )

        expired = table.c.expires_at <= now

        statement = statement.on_conflict_do_update(
            index_elements=[table.c.key],
            set_={
                "attempts": case(
                    (expired, 1),
                    else_=table.c.attempts + 1,
                ),
                "window_started_at": case(
                    (expired, now),
                    else_=table.c.window_started_at,
                ),
                "expires_at": case(
                    (expired, expires_at),
                    else_=table.c.expires_at,
                ),
            },
        ).returning(
            table.c.attempts,
            table.c.expires_at,
        )

        row = db.execute(statement).one()
        db.commit()

        attempts = row.attempts
        expiration = row.expires_at

        current_time = datetime.now(timezone.utc)

        remaining = max(
            1,
            int(
                (
                    expiration - current_time
                ).total_seconds()
            ) + 1,
        )

        return RateLimitResult(
            allowed=attempts <= limit,
            attempts=attempts,
            retry_after=0 if attempts <= limit else remaining,
        )

    def _record_sqlite(
        self,
        db: Session,
        *,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitResult:
        """Implementación compatible con las pruebas SQLite."""

        now = datetime.now(timezone.utc)

        record = db.scalar(
            select(AuthRateLimit).where(AuthRateLimit.key == key)
        )

        if record is None:
            record = AuthRateLimit(
                key=key,
                attempts=1,
                window_started_at=now,
                expires_at=now + timedelta(seconds=window_seconds),
            )
            db.add(record)
        else:
            expiration = record.expires_at

            if expiration.tzinfo is None:
                expiration = expiration.replace(tzinfo=timezone.utc)

            if expiration <= now:
                record.attempts = 1
                record.window_started_at = now
                record.expires_at = now + timedelta(
                    seconds=window_seconds
                )
            else:
                record.attempts += 1

        db.commit()
        db.refresh(record)

        expiration = record.expires_at

        if expiration.tzinfo is None:
            expiration = expiration.replace(tzinfo=timezone.utc)

        remaining = max(
            1,
            int((expiration - now).total_seconds()) + 1,
        )

        return RateLimitResult(
            allowed=record.attempts <= limit,
            attempts=record.attempts,
            retry_after=(
                0 if record.attempts <= limit else remaining
            ),
        )


rate_limit_repository = RateLimitRepository()
