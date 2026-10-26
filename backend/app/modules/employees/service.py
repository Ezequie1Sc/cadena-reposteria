"""Lógica de negocio para la administración de empleados."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.branches.model import Branch
from app.modules.employees.repository import employee_repository
from app.modules.employees.schemas import (
    EmployeeCreate,
    EmployeeResponse,
    EmployeeUpdate,
)
from app.shared.models.user_reference import users_reference


class EmployeeService:
    """Servicio de operaciones y validaciones de empleados."""

    @staticmethod
    def _response(employee) -> EmployeeResponse:
        return EmployeeResponse.model_validate(employee)

    @staticmethod
    def _validate_required_fields(changes: dict) -> None:
        required_fields = {
            "usuario_id",
            "sucursal_id",
            "numero_empleado",
            "puesto",
        }

        if any(
            field in changes and changes[field] is None
            for field in required_fields
        ):
            raise HTTPException(
                status_code=422,
                detail="Los campos obligatorios no pueden ser nulos",
            )

    @staticmethod
    def _validate_user(db: Session, usuario_id: int) -> None:
        query = select(users_reference.c.id).where(
            users_reference.c.id == usuario_id
        )

        if db.scalar(query) is None:
            raise HTTPException(
                status_code=422,
                detail="El usuario indicado no existe",
            )

    @staticmethod
    def _validate_branch(db: Session, sucursal_id: int) -> None:
        branch = db.get(Branch, sucursal_id)

        if branch is None:
            raise HTTPException(
                status_code=422,
                detail="La sucursal indicada no existe",
            )

        if not branch.activo:
            raise HTTPException(
                status_code=422,
                detail="No se pueden asignar empleados a una sucursal inactiva",
            )

    @staticmethod
    def _validate_employee_number(
        db: Session,
        numero_empleado: str,
        exclude_employee_id: int | None = None,
    ) -> None:
        existing = employee_repository.get_by_employee_number(
            db,
            numero_empleado,
        )

        if existing is not None and existing.id != exclude_employee_id:
            raise HTTPException(
                status_code=409,
                detail="Ya existe un empleado con este número",
            )

    @staticmethod
    def _validate_unique_user(
        db: Session,
        usuario_id: int,
        exclude_employee_id: int | None = None,
    ) -> None:
        existing = employee_repository.get_by_user_id(
            db,
            usuario_id,
        )

        if existing is not None and existing.id != exclude_employee_id:
            raise HTTPException(
                status_code=409,
                detail="El usuario ya está asociado a otro empleado",
            )

    def get_employees(
        self,
        db: Session,
        busqueda: str | None = None,
        sucursal_id: int | None = None,
        solo_activos: bool = True,
    ) -> list[EmployeeResponse]:
        employees = employee_repository.get_all(
            db=db,
            busqueda=busqueda,
            sucursal_id=sucursal_id,
            solo_activos=solo_activos,
        )

        return [self._response(employee) for employee in employees]

    def get_employee_by_id(
        self,
        db: Session,
        employee_id: int,
    ) -> EmployeeResponse | None:
        employee = employee_repository.get_by_id(db, employee_id)

        if employee is None:
            return None

        return self._response(employee)

    def create_employee(
        self,
        db: Session,
        data: EmployeeCreate,
    ) -> EmployeeResponse:
        self._validate_user(db, data.usuario_id)
        self._validate_branch(db, data.sucursal_id)
        self._validate_employee_number(db, data.numero_empleado)
        self._validate_unique_user(db, data.usuario_id)

        try:
            employee = employee_repository.create(db, data)
            db.commit()
            db.refresh(employee)

            return self._response(employee)

        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="No se pudo registrar el empleado por un conflicto de datos",
            ) from exc

    def update_employee(
        self,
        db: Session,
        employee_id: int,
        data: EmployeeUpdate,
    ) -> EmployeeResponse:
        employee = employee_repository.get_by_id(db, employee_id)

        if employee is None:
            raise HTTPException(
                status_code=404,
                detail="Empleado no encontrado",
            )

        changes = data.model_dump(exclude_unset=True)
        self._validate_required_fields(changes)

        if "usuario_id" in changes:
            self._validate_user(db, changes["usuario_id"])
            self._validate_unique_user(
                db,
                changes["usuario_id"],
                exclude_employee_id=employee_id,
            )

        if "sucursal_id" in changes:
            self._validate_branch(db, changes["sucursal_id"])

        if "numero_empleado" in changes:
            self._validate_employee_number(
                db,
                changes["numero_empleado"],
                exclude_employee_id=employee_id,
            )

        try:
            employee = employee_repository.update(db, employee, data)
            db.commit()
            db.refresh(employee)

            return self._response(employee)

        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="No se pudo actualizar el empleado por un conflicto de datos",
            ) from exc

    def deactivate_employee(
        self,
        db: Session,
        employee_id: int,
    ) -> EmployeeResponse:
        employee = employee_repository.get_by_id(db, employee_id)

        if employee is None:
            raise HTTPException(
                status_code=404,
                detail="Empleado no encontrado",
            )

        if employee.activo:
            try:
                employee = employee_repository.deactivate(db, employee)
                db.commit()
                db.refresh(employee)

            except IntegrityError as exc:
                db.rollback()
                raise HTTPException(
                    status_code=409,
                    detail="No se pudo desactivar el empleado",
                ) from exc

        return self._response(employee)

    def reactivate_employee(
        self,
        db: Session,
        employee_id: int,
    ) -> EmployeeResponse:
        employee = employee_repository.get_by_id(db, employee_id)

        if employee is None:
            raise HTTPException(
                status_code=404,
                detail="Empleado no encontrado",
            )

        if not employee.activo:
            self._validate_user(db, employee.usuario_id)
            self._validate_branch(db, employee.sucursal_id)

            try:
                employee = employee_repository.reactivate(db, employee)
                db.commit()
                db.refresh(employee)

            except IntegrityError as exc:
                db.rollback()
                raise HTTPException(
                    status_code=409,
                    detail="No se pudo reactivar el empleado",
                ) from exc

        return self._response(employee)


employee_service = EmployeeService()