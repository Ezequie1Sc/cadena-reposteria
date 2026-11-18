"""Primitivas comunes: autorización, transacciones e idempotencia durable."""

from datetime import datetime, timezone
from decimal import Decimal
from functools import wraps
from hashlib import sha256
import json
from typing import Annotated
from fastapi import Header, HTTPException, Query, Depends
from pydantic import BaseModel, ConfigDict, Field, model_validator, AwareDatetime
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from app.shared.commerce_models import CommercialEvent, IdempotencyRecord
from app.modules.users.model import User
from app.modules.customers.model import Customer
from app.core.permissions import scope_branch, RoleID

Key = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=100,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    ),
]
PositiveID = Annotated[int, Field(gt=0)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DateFilters(BaseModel):
    desde: datetime | None = None
    hasta: datetime | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        for dt in (self.desde, self.hasta):
            if dt is not None and dt.utcoffset() is None:
                raise ValueError("Las fechas requieren zona horaria")
        if self.desde and self.hasta and self.desde >= self.hasta:
            raise ValueError("desde debe ser anterior a hasta")
        return self


class EventResponse(ORMModel):
    id: int
    recurso: str
    recurso_id: int
    anterior: str | None
    estado: str
    usuario_id: int
    motivo: str | None
    created_at: datetime


class CancelRequest(StrictModel):
    motivo: str = Field(min_length=3, max_length=500)
    reembolso_referencia: str | None = Field(default=None, min_length=3, max_length=255)


def utcnow():
    return datetime.now(timezone.utc)


def expired(value):
    return (
        value is not None
        and value.replace(tzinfo=value.tzinfo or timezone.utc) <= utcnow()
    )


def money(value):
    result = Decimal(str(value)).quantize(Decimal("0.01"))
    if not result.is_finite() or result < 0 or result > Decimal("9999999999.99"):
        raise HTTPException(409, "Importe fuera de rango")
    return result


def atomic(fn):
    @wraps(fn)
    def call(db, *args, **kwargs):
        try:
            result = fn(db, *args, **kwargs)
            db.commit()
            return result
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                409,
                "Conflicto de integridad; consulta la operación antes de reintentar",
            ) from None
        except Exception:
            db.rollback()
            raise

    return call


def own_customer(db, actor):
    customer = db.scalar(
        select(Customer)
        .where(Customer.usuario_id == actor.id)
        .with_for_update(read=True)
    )
    if customer is None or not customer.activo:
        raise HTTPException(403, "Se requiere un perfil de cliente activo")
    return customer


def authorize(db, actor, resource):
    if actor.rol_id == RoleID.CLIENTE:
        if own_customer(db, actor).id != resource.cliente_id:
            raise HTTPException(403, "No tienes acceso a esta operación")
    else:
        scope_branch(db, actor, resource.sucursal_id)


def scope_query(db, actor, stmt, model, branch=None):
    if actor.rol_id == RoleID.CLIENTE:
        stmt = stmt.where(model.cliente_id == own_customer(db, actor).id)
        if branch is not None:
            stmt = stmt.where(model.sucursal_id == branch)
    else:
        branch = scope_branch(db, actor, branch)
        if branch is not None:
            stmt = stmt.where(model.sucursal_id == branch)
    return stmt


def dated(stmt, column, dates):
    if dates.desde:
        stmt = stmt.where(column >= dates.desde)
    if dates.hasta:
        stmt = stmt.where(column < dates.hasta)
    return stmt


def page(db, stmt, limit=20, offset=0):
    count = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    return count, list(db.scalars(stmt.limit(limit).offset(offset)).unique())


def record(db, resource, obj, actor, previous=None, reason=None):
    db.add(
        CommercialEvent(
            recurso=resource,
            recurso_id=obj.id,
            anterior=previous,
            estado=obj.estado,
            usuario_id=actor.id,
            motivo=reason,
        )
    )
    db.flush()


def history(db, resource, resource_id, limit=100, offset=0):
    return list(
        db.scalars(
            select(CommercialEvent)
            .where(
                CommercialEvent.recurso == resource,
                CommercialEvent.recurso_id == resource_id,
            )
            .order_by(CommercialEvent.id)
            .limit(limit)
            .offset(offset)
        )
    )


def begin_idempotency(db, actor, operation, key, payload):
    # A row lock serializes same-actor creates across workers; unique constraint is the final guard.
    db.execute(select(User.id).where(User.id == actor.id).with_for_update())
    digest = sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    prior = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.usuario_id == actor.id,
            IdempotencyRecord.operacion == operation,
            IdempotencyRecord.clave == key,
        )
    )
    if prior and prior.huella != digest:
        raise HTTPException(409, "Idempotency-Key ya utilizada con otro contenido")
    return prior.recurso_id if prior else None, digest


def finish_idempotency(db, actor, operation, key, digest, resource_id):
    db.add(
        IdempotencyRecord(
            usuario_id=actor.id,
            operacion=operation,
            clave=key,
            huella=digest,
            recurso_id=resource_id,
        )
    )
    db.flush()


def date_filters(
    desde: Annotated[AwareDatetime | None, Query()] = None,
    hasta: Annotated[AwareDatetime | None, Query()] = None,
):
    if desde and hasta and desde >= hasta:
        raise HTTPException(422, "desde debe ser anterior a hasta")
    return DateFilters(desde=desde, hasta=hasta)


Dates = Annotated[DateFilters, Depends(date_filters)]
