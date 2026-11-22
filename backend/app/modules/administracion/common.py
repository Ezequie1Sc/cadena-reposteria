from fastapi import HTTPException
from sqlalchemy import text


def execute(db, sql, **params):
    return db.execute(text(sql), params)


def row(db, sql, **params):
    return execute(db, sql, **params).mappings().one_or_none()


def required(value, message="Recurso no encontrado"):
    if value is None:
        raise HTTPException(404, message)
    return value


def rows(db, sql, **params):
    return execute(db, sql, **params).mappings().all()


def reserve_code(db, employee=False):
    sequence = "public.empleados_id_seq" if employee else "public.productos_id_seq"
    prefix = "EMP" if employee else "PROD"
    identifier = execute(
        db, "SELECT nextval(CAST(:seq AS regclass))", seq=sequence
    ).scalar_one()
    return identifier, f"{prefix}-{identifier:05d}"
