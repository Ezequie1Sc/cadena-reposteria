
"""Modelo de persistencia para límites de autenticación."""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AuthRateLimit(Base):
    """
    Contador compartido de solicitudes de autenticación.

    Las claves se generan mediante HMAC para evitar almacenar
    identificadores personales directamente en PostgreSQL.

    Las actualizaciones atómicas y la expiración de ventanas
    se implementarán en la capa de repositorio.
    """

    __tablename__ = "auth_rate_limits"

    key: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    window_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
