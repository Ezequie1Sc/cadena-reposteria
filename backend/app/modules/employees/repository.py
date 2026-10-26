"""Repositorio de acceso a datos para empleados."""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.employees.model import Employee
from app.modules.employees.schemas import (
    EmployeeCreate,
    EmployeeUpdate,
)


class EmployeeRepository:
    """Operaciones de persistencia para empleados."""

    def get_all(
        self,
        db: Session,
        busqueda: str | None = None,
        sucursal_id: int | None = None,
        solo_activos: bool = True,
    ) -> list[Employee]:
        query = select(Employee)

        if solo_activos:
            query = query.where(Employee.activo.is_(True))

        if sucursal_id is not None:
            query = query.where(
                Employee.sucursal_id == sucursal_id
            )

        if busqueda:
            termino = busqueda.strip()

            if termino:
                query = query.where(
                    or_(
                        Employee.numero_empleado.ilike(
                            f"%{termino}%"
                        ),
                        Employee.puesto.ilike(
                            f"%{termino}%"
                        ),
                    )
                )

        query = query.order_by(
            Employee.numero_empleado,
            Employee.id,
        )

        return list(db.scalars(query).all())

    def get_by_id(
        self,
        db: Session,
        employee_id: int,
    ) -> Employee | None:
        return db.get(Employee, employee_id)

    def get_by_employee_number(
        self,
        db: Session,
        numero_empleado: str,
    ) -> Employee | None:
        query = select(Employee).where(
            func.lower(Employee.numero_empleado)
            == numero_empleado.strip().lower()
        )

        return db.scalar(query)

    def get_by_user_id(
        self,
        db: Session,
        usuario_id: int,
    ) -> Employee | None:
        query = select(Employee).where(
            Employee.usuario_id == usuario_id
        )

        return db.scalar(query)

    def create(
        self,
        db: Session,
        data: EmployeeCreate,
    ) -> Employee:
        employee = Employee(**data.model_dump())

        db.add(employee)
        db.flush()
        db.refresh(employee)

        return employee

    def update(
        self,
        db: Session,
        employee: Employee,
        data: EmployeeUpdate,
    ) -> Employee:
        changes = data.model_dump(exclude_unset=True)

        for field, value in changes.items():
            setattr(employee, field, value)

        if changes:
            db.flush()
            db.refresh(employee)

        return employee

    def deactivate(
        self,
        db: Session,
        employee: Employee,
    ) -> Employee:
        employee.activo = False

        db.flush()
        db.refresh(employee)

        return employee

    def reactivate(
        self,
        db: Session,
        employee: Employee,
    ) -> Employee:
        employee.activo = True

        db.flush()
        db.refresh(employee)

        return employee


employee_repository = EmployeeRepository()