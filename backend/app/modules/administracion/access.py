from fastapi import HTTPException

from app.core.config import settings
from app.core.roles import RoleID

from .common import row


def check_employee_session(db, user):
    if settings.administracion_habilitada and user.rol_id == RoleID.EMPLEADO:
        from app.core.permissions import employee_branch_id

        employee_branch_id(db, user)
        if row(
            db,
            """SELECT 1 FROM gestion_interna.expediente x JOIN public.empleados e ON e.id=x.empleado_id
                   WHERE e.usuario_id=:id AND x.estado <> 'APROBADO'""",
            id=user.id,
        ):
            raise HTTPException(403, "Cuenta pendiente de aprobación")


def administrative_contract(message):
    if settings.administracion_habilitada:
        raise HTTPException(409, message)


def protect_user(db, uid, fields):
    if not settings.administracion_habilitada:
        return
    item = row(
        db,
        """SELECT x.estado FROM gestion_interna.expediente x
        JOIN public.empleados e ON e.id=x.empleado_id WHERE e.usuario_id=:id FOR UPDATE OF x""",
        id=uid,
    )
    if item and (item["estado"] != "APROBADO" or fields & {"rol_id", "email"}):
        raise HTTPException(
            409, "La identidad está vinculada a un expediente de incorporación"
        )


def protect_employee(db, identifier):
    if settings.administracion_habilitada:
        state = row(
            db,
            "SELECT estado FROM gestion_interna.expediente WHERE empleado_id=:id FOR UPDATE",
            id=identifier,
        )
        if state and state["estado"] != "APROBADO":
            raise HTTPException(409, "El empleado requiere aprobación")
