"""Endpoints REST para la administración de empleados."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.employees.schemas import (
    EmployeeCreate,
    EmployeeListResponse,
    EmployeeResponse,
    EmployeeUpdate,
)
from app.modules.employees.service import employee_service


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/empleados",
    tags=["Empleados"],
)

DbSession = Annotated[Session, Depends(get_db)]


@router.get(
    "",
    response_model=EmployeeListResponse,
)
def list_employees(
    db: DbSession,
    busqueda: str | None = Query(default=None, max_length=100),
    sucursal_id: int | None = Query(default=None, gt=0),
    solo_activos: bool = True,
):
    """Listar empleados con filtros opcionales."""

    try:
        employees = employee_service.get_employees(
            db=db,
            busqueda=busqueda,
            sucursal_id=sucursal_id,
            solo_activos=solo_activos,
        )

        return EmployeeListResponse(
            total=len(employees),
            empleados=employees,
        )

    except SQLAlchemyError as exc:
        logger.exception("Error al listar empleados")
        raise HTTPException(
            status_code=503,
            detail="No se pudo consultar la lista de empleados",
        ) from exc


@router.get(
    "/{employee_id}",
    response_model=EmployeeResponse,
)
def get_employee(
    employee_id: int,
    db: DbSession,
):
    """Consultar un empleado por su identificador."""

    try:
        employee = employee_service.get_employee_by_id(
            db,
            employee_id,
        )

        if employee is None:
            raise HTTPException(
                status_code=404,
                detail="Empleado no encontrado",
            )

        return employee

    except SQLAlchemyError as exc:
        logger.exception("Error al consultar empleado")
        raise HTTPException(
            status_code=503,
            detail="No se pudo consultar el empleado",
        ) from exc


@router.post(
    "",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_employee(
    data: EmployeeCreate,
    db: DbSession,
):
    """Registrar un nuevo empleado."""

    try:
        return employee_service.create_employee(
            db,
            data,
        )

    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Error al registrar empleado")
        raise HTTPException(
            status_code=503,
            detail="No se pudo registrar el empleado",
        ) from exc


@router.patch(
    "/{employee_id}",
    response_model=EmployeeResponse,
)
def update_employee(
    employee_id: int,
    data: EmployeeUpdate,
    db: DbSession,
):
    """Actualizar parcialmente los datos de un empleado."""

    try:
        return employee_service.update_employee(
            db,
            employee_id,
            data,
        )

    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Error al actualizar empleado")
        raise HTTPException(
            status_code=503,
            detail="No se pudo actualizar el empleado",
        ) from exc


@router.delete(
    "/{employee_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def deactivate_employee(
    employee_id: int,
    db: DbSession,
):
    """Desactivar un empleado sin eliminar su registro."""

    try:
        employee_service.deactivate_employee(
            db,
            employee_id,
        )

        return Response(
            status_code=status.HTTP_204_NO_CONTENT,
        )

    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Error al desactivar empleado")
        raise HTTPException(
            status_code=503,
            detail="No se pudo desactivar el empleado",
        ) from exc


@router.patch(
    "/{employee_id}/reactivar",
    response_model=EmployeeResponse,
)
def reactivate_employee(
    employee_id: int,
    db: DbSession,
):
    """Reactivar un empleado previamente desactivado."""

    try:
        return employee_service.reactivate_employee(
            db,
            employee_id,
        )

    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Error al reactivar empleado")
        raise HTTPException(
            status_code=503,
            detail="No se pudo reactivar el empleado",
        ) from exc