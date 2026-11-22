import hmac
import secrets
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import EmailStr, Field, SecretStr

from app.core.auth import CurrentUser, DbSession
from app.core.config import settings
from app.core.permissions import AdminUser
from app.core.roles import RoleID, catalog_role_active
from app.core.security import hash_password
from app.modules.users.model import User
from app.shared.commerce import (
    Key,
    PositiveID,
    StrictModel,
    atomic,
    begin_idempotency,
    finish_idempotency,
)

from .common import execute, required, reserve_code, row, rows
from .company import applicable
from .mail import portal, queue
from .responses import EmployeeProfile, ReviewEvent, Status

router = APIRouter(tags=["Incorporación"])
PROFILE = """SELECT x.empleado_id,x.estado,x.email,x.creado,x.bienvenida_vista,
    e.numero_empleado,e.puesto,e.sucursal_id,e.usuario_id,u.nombre,u.apellido,s.nombre AS sucursal
    FROM gestion_interna.expediente x JOIN public.empleados e ON e.id=x.empleado_id
    JOIN public.usuarios u ON u.id=e.usuario_id JOIN public.sucursales s ON s.id=e.sucursal_id"""


class Hire(StrictModel):
    nombre: str = Field(min_length=1, max_length=100)
    apellido: str = Field(min_length=1, max_length=100)
    email: EmailStr = Field(max_length=254)
    puesto: str = Field(min_length=1, max_length=100)
    sucursal_id: int = Field(gt=0)


class Token(StrictModel):
    token: str = Field(min_length=40, max_length=100)


class Verification(Token):
    codigo: str = Field(pattern=r"^[0-9]{6}$")


class Submission(Token):
    codigo: str = Field(pattern=r"^(?:[0-9]{6}|[A-Za-z0-9_-]{43})$")
    password: SecretStr = Field(min_length=12, max_length=128)
    nombre: str = Field(min_length=1, max_length=100)
    apellido: str = Field(min_length=1, max_length=100)


class Decision(StrictModel):
    accion: Literal["aprobar", "rechazar", "correccion", "revocar", "reinvitar"]
    motivo: str | None = Field(None, min_length=1, max_length=500)


def digest(value):
    return hmac.digest(settings.jwt_secret_key.encode(), value.encode(), "sha256").hex()


def event(db, identifier, action, actor=None, reason=None):
    execute(
        db,
        """INSERT INTO gestion_interna.evento(empleado_id,actor_id,accion,motivo,fecha)
                   VALUES(:id,:actor,:action,:reason,clock_timestamp())""",
        id=identifier,
        actor=actor,
        action=action,
        reason=reason,
    )


def invite(db, emp, state="INVITADO"):
    token = secrets.token_urlsafe(40)
    execute(
        db,
        """UPDATE gestion_interna.expediente SET estado=:state,token_hash=:h,
        vence=now()+interval '48 hours', codigo_hash=NULL,codigo_vence=NULL,siguiente_codigo=NULL,
        intentos=0,envios=0 WHERE empleado_id=:id""",
        state=state,
        h=digest(token),
        id=emp["empleado_id"],
    )
    queue(
        db,
        emp,
        "invitacion",
        "Invitación de incorporación",
        [emp["nombre"]],
        url=portal() + "/incorporacion#token=" + token,
    )


def employee_role(db):
    if catalog_role_active(db, RoleID.EMPLEADO, lock=True) is not True:
        raise HTTPException(503, "El rol Empleado no está disponible")
    return RoleID.EMPLEADO


def hire(db, data, actor_id):
    email = str(data.email).lower()
    role = employee_role(db)
    if not row(
        db,
        "SELECT id FROM public.sucursales WHERE id=:id AND activo FOR SHARE",
        id=data.sucursal_id,
    ):
        raise HTTPException(422, "Sucursal no disponible")
    if row(
        db,
        "SELECT id FROM public.usuarios WHERE lower(btrim(email))=:email LIMIT 1",
        email=email,
    ):
        raise HTTPException(409, "El correo ya tiene cuenta")
    # Cuenta inactiva con verificador imposible para Argon2; no se crea contraseña temporal.
    user = User(
        rol_id=role,
        nombre=data.nombre,
        apellido=data.apellido,
        email=email,
        password_hash="!pendiente",
        activo=False,
    )
    db.add(user)
    db.flush()
    identifier, code = reserve_code(db, employee=True)
    execute(
        db,
        """INSERT INTO public.empleados(id,usuario_id,sucursal_id,numero_empleado,puesto,activo)
        OVERRIDING SYSTEM VALUE VALUES(:id,:uid,:branch,:code,:position,false)""",
        id=identifier,
        uid=user.id,
        branch=data.sucursal_id,
        code=code,
        position=data.puesto,
    )
    execute(
        db,
        "INSERT INTO gestion_interna.expediente(empleado_id,email,estado) VALUES(:id,:email,'INVITADO')",
        id=identifier,
        email=email,
    )
    emp = row(db, PROFILE + " WHERE empleado_id=:id", id=identifier)
    invite(db, emp)
    event(db, identifier, "ALTA", actor_id)
    return identifier


@atomic
def register(db, actor, data, key):
    prior, fingerprint = begin_idempotency(
        db, actor, "alta_empleado", key, data.model_dump(mode="json")
    )
    if prior is None:
        prior = hire(db, data, actor.id)
        finish_idempotency(db, actor, "alta_empleado", key, fingerprint, prior)
    return row(db, PROFILE + " WHERE empleado_id=:id", id=prior)


@router.post(
    "/administracion/empleados", status_code=201, response_model=EmployeeProfile
)
def register_employee(
    data: Hire, db: DbSession, actor: AdminUser, idempotency_key: Key
):
    return register(db, actor, data, idempotency_key)


def eligible(db, token):
    entry = row(
        db,
        """SELECT *, siguiente_codigo>now() AS espera, codigo_vence>now() AS vigente
        FROM gestion_interna.expediente WHERE token_hash=:h AND vence>now()
        AND estado IN ('INVITADO','CORRECCION') FOR UPDATE""",
        h=digest(token),
    )
    if not entry:
        raise HTTPException(400, "Invitación no disponible")
    return entry


def throttle(request: Request, db: DbSession):
    from app.core.rate_limit import _client_ip, _rate_limit_key
    from app.modules.auth.rate_limit_repository import rate_limit_repository

    key = _rate_limit_key(category="incorporacion", identifier=_client_ip(request))
    result = rate_limit_repository.record_attempt(
        db, key=key, limit=120, window_seconds=600
    )
    if not result.allowed:
        raise HTTPException(
            429, "Demasiados intentos", headers={"Retry-After": str(result.retry_after)}
        )


@router.post("/incorporacion/codigo", status_code=202, dependencies=[Depends(throttle)])
def send_code(data: Token, db: DbSession):
    emp = eligible(db, data.token)
    if emp["espera"] or emp["envios"] >= 5 or emp["intentos"] >= 5:
        raise HTTPException(429, "Límite de verificación alcanzado")
    code = f"{secrets.randbelow(1000000):06d}"
    execute(
        db,
        """UPDATE gestion_interna.expediente SET codigo_hash=:h,codigo_vence=now()+interval '10 minutes',
        siguiente_codigo=now()+interval '60 seconds',envios=envios+1 WHERE empleado_id=:id""",
        h=digest(data.token + code),
        id=emp["empleado_id"],
    )
    queue(
        db, emp, "codigo", "Verificación de correo", [code, "Vigencia de diez minutos."]
    )
    event(db, emp["empleado_id"], "CODIGO_EMITIDO")
    db.commit()
    return {"enviado_a_cola": True}


def check_proof(db, emp, data):
    if emp["intentos"] >= 5:
        raise HTTPException(429, "Límite de verificación alcanzado")
    if not emp["vigente"] or not hmac.compare_digest(
        emp["codigo_hash"] or "", digest(data.token + data.codigo)
    ):
        execute(
            db,
            "UPDATE gestion_interna.expediente SET intentos=intentos+1 WHERE empleado_id=:id",
            id=emp["empleado_id"],
        )
        db.commit()
        raise HTTPException(400, "Código inválido o vencido")


@router.post("/incorporacion/verificar", dependencies=[Depends(throttle)])
def verify(data: Verification, db: DbSession):
    emp = eligible(db, data.token)
    check_proof(db, emp, data)
    proof = secrets.token_urlsafe(32)
    execute(
        db,
        """UPDATE gestion_interna.expediente SET codigo_hash=:h,
        codigo_vence=now()+interval '10 minutes' WHERE empleado_id=:id""",
        h=digest(data.token + proof),
        id=emp["empleado_id"],
    )
    event(db, emp["empleado_id"], "CORREO_VERIFICADO")
    db.commit()
    return {"comprobante": proof}


@router.post(
    "/incorporacion/solicitud", response_model=Status, dependencies=[Depends(throttle)]
)
def submit(data: Submission, db: DbSession):
    emp = eligible(db, data.token)
    check_proof(db, emp, data)
    password = data.password.get_secret_value()
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        raise HTTPException(422, "La contraseña requiere letras y números")
    updated = execute(
        db,
        """UPDATE public.usuarios u SET nombre=:name,apellido=:last,password_hash=:pw
        FROM public.empleados e WHERE e.id=:id AND u.id=e.usuario_id AND NOT u.activo AND u.rol_id=:role""",
        role=employee_role(db),
        name=data.nombre,
        last=data.apellido,
        pw=hash_password(password),
        id=emp["empleado_id"],
    )
    if updated.rowcount != 1:
        raise HTTPException(409, "La cuenta requiere revisión administrativa")
    execute(
        db,
        """UPDATE gestion_interna.expediente SET estado='PENDIENTE',token_hash=NULL,codigo_hash=NULL
        WHERE empleado_id=:id""",
        id=emp["empleado_id"],
    )
    event(db, emp["empleado_id"], "SOLICITUD_VERIFICADA")
    queue(
        db,
        emp,
        "solicitud",
        "Solicitud recibida",
        ["Tu solicitud está pendiente de aprobación."],
    )
    db.commit()
    return {"estado": "PENDIENTE"}


@router.get("/administracion/solicitudes", response_model=list[EmployeeProfile])
def applications(
    db: DbSession, actor: AdminUser, estado: str = "PENDIENTE", offset: int = 0
):
    return rows(
        db,
        PROFILE
        + " WHERE x.estado=:state ORDER BY x.creado,x.empleado_id LIMIT 100 OFFSET :off",
        state=estado,
        off=max(0, offset),
    )


@router.get(
    "/administracion/solicitudes/{identifier}/historial",
    response_model=list[ReviewEvent],
)
def history(identifier: PositiveID, db: DbSession, actor: AdminUser):
    return rows(
        db,
        "SELECT accion,actor_id,fecha,motivo FROM gestion_interna.evento WHERE empleado_id=:id ORDER BY id",
        id=identifier,
    )


@atomic
def decide(db, actor, identifier, data, key):
    prior, fingerprint = begin_idempotency(
        db,
        actor,
        "decision_empleado",
        key,
        {"empleado": identifier, **data.model_dump()},
    )
    action = data.accion
    states = {
        "aprobar": "APROBADO",
        "rechazar": "RECHAZADO",
        "revocar": "REVOCADO",
        "correccion": "CORRECCION",
        "reinvitar": "INVITADO",
    }
    state = states[action]
    if prior:
        return {"estado": state}
    emp = required(
        row(db, PROFILE + " WHERE empleado_id=:id FOR UPDATE OF x,e,u,s", id=identifier)
    )
    if action in ("correccion", "rechazar", "revocar") and not data.motivo:
        raise HTTPException(422, "Indica el motivo")
    if emp["estado"] == state and action in ("aprobar", "revocar"):
        finish_idempotency(db, actor, "decision_empleado", key, fingerprint, identifier)
        return {"estado": state}
    allowed = {
        "aprobar": {"PENDIENTE"},
        "rechazar": {"PENDIENTE"},
        "correccion": {"PENDIENTE"},
        "reinvitar": {"INVITADO", "CORRECCION", "REVOCADO", "RECHAZADO"},
        "revocar": {"INVITADO", "CORRECCION", "PENDIENTE", "APROBADO", "RECHAZADO"},
    }
    if emp["estado"] not in allowed[action]:
        raise HTTPException(409, "Transición de incorporación inválida")
    execute(
        db,
        "UPDATE gestion_interna.expediente SET estado=:state,token_hash=NULL,codigo_hash=NULL WHERE empleado_id=:id",
        state=state,
        id=identifier,
    )
    execute(
        db,
        """UPDATE gestion_interna.correo SET estado='CANCELADO',contenido=NULL
        WHERE empleado_id=:id AND tipo IN ('codigo','invitacion') AND estado='LISTO'""",
        id=identifier,
    )
    if action == "revocar":
        execute(
            db,
            "UPDATE public.usuarios SET activo=false WHERE id=:id",
            id=emp["usuario_id"],
        )
        execute(
            db, "UPDATE public.empleados SET activo=false WHERE id=:id", id=identifier
        )
        execute(
            db,
            """UPDATE gestion_interna.correo SET estado='CANCELADO',contenido=NULL
            WHERE empleado_id=:id AND estado='LISTO'""",
            id=identifier,
        )
    if action in ("correccion", "reinvitar"):
        invite(db, emp, state)
    if action == "aprobar":
        role = employee_role(db)
        if not row(
            db,
            """SELECT u.id FROM public.usuarios u,public.sucursales s WHERE u.id=:uid AND
            s.id=:branch AND s.activo AND u.rol_id=:role AND lower(u.email)=:email AND u.password_hash LIKE '$argon2id$%'""",
            role=role,
            uid=emp["usuario_id"],
            branch=emp["sucursal_id"],
            email=emp["email"],
        ):
            raise HTTPException(409, "Identidad o asignación incompatible")
        brand = execute(
            db, "SELECT datos FROM gestion_interna.identidad WHERE id=1"
        ).scalar_one_or_none()
        if not brand:
            raise HTTPException(
                409, "Configura la identidad empresarial antes de aprobar"
            )
        execute(
            db,
            "UPDATE public.usuarios SET activo=true WHERE id=:id",
            id=emp["usuario_id"],
        )
        execute(
            db, "UPDATE public.empleados SET activo=true WHERE id=:id", id=identifier
        )
        queue(db, emp, "aprobacion", "Solicitud aprobada", [emp["nombre"]])
        details = [
            emp["nombre"] + " " + emp["apellido"],
            emp["puesto"],
            emp["sucursal"],
            emp["numero_empleado"],
            brand["mensaje"],
        ]
        details.extend(
            b["nombre"] + " — " + b["condiciones"] for b in applicable(db, emp)
        )
        queue(
            db,
            emp,
            "bienvenida",
            "¡Bienvenido a la familia de " + brand["nombre"] + "!",
            details + [brand["firma"], brand["contacto"]],
            url=portal(),
            brand=brand,
        )
    elif action in ("rechazar", "correccion"):
        queue(db, emp, action, "Actualización de solicitud", [state, data.motivo])
    finish_idempotency(db, actor, "decision_empleado", key, fingerprint, identifier)
    event(db, identifier, state, actor.id, data.motivo)
    return {"estado": state}


@router.post("/administracion/solicitudes/{identifier}/decision", response_model=Status)
def decision(
    identifier: PositiveID,
    data: Decision,
    db: DbSession,
    actor: AdminUser,
    idempotency_key: Key,
):
    return decide(db, actor, identifier, data, idempotency_key)


@router.get("/empleado/bienvenida")
def welcome(db: DbSession, actor: CurrentUser):
    if actor.rol_id != RoleID.EMPLEADO:
        raise HTTPException(403, "Acceso exclusivo del empleado")
    emp = row(
        db,
        PROFILE
        + " WHERE u.id=:id AND x.estado='APROBADO' AND u.rol_id=:role AND e.activo AND s.activo",
        id=actor.id,
        role=RoleID.EMPLEADO,
    )
    if not emp:
        return {"pendiente": False}
    return {
        "pendiente": emp["bienvenida_vista"] is None,
        "empleado": emp,
        "beneficios": applicable(db, emp),
        "identidad": execute(
            db, "SELECT datos FROM gestion_interna.identidad WHERE id=1"
        ).scalar_one_or_none(),
    }


@router.post("/empleado/bienvenida/vista")
def acknowledge(db: DbSession, actor: CurrentUser):
    if actor.rol_id != RoleID.EMPLEADO:
        raise HTTPException(403, "Acceso exclusivo del empleado")
    execute(
        db,
        """UPDATE gestion_interna.expediente x SET bienvenida_vista=coalesce(bienvenida_vista,now())
        FROM public.empleados e WHERE e.id=x.empleado_id AND e.usuario_id=:id AND x.estado='APROBADO'""",
        id=actor.id,
    )
    db.commit()
    return {"pendiente": False}
