
import json
import uuid
from urllib.parse import urlsplit

import httpx
from cryptography.fernet import Fernet
from fastapi import HTTPException

from app.core.config import settings

from .common import execute, row
from .email_templates import render_email


def cipher():
    if not settings.correo_clave_cifrado:
        raise HTTPException(
            503,
            "Falta configurar el cifrado de correo",
        )

    return Fernet(
        settings.correo_clave_cifrado.encode()
    )


def portal():
    url = (settings.portal_url or "").rstrip("/")

    try:
        parsed = urlsplit(url)

        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("URL inválida")

    except ValueError:
        raise HTTPException(
            503,
            "Configura la URL HTTPS del portal",
        )

    return url


def get_email_brand(db):
    identity = execute(
        db,
        """
        SELECT datos
        FROM gestion_interna.identidad
        WHERE id = 1
        """,
    ).scalar_one_or_none()

    if isinstance(identity, str):
        try:
            identity = json.loads(identity)
        except (ValueError, TypeError):
            identity = None

    if not isinstance(identity, dict):
        identity = {}

    return {
        "nombre": "DulceGestión",
        "color": "#49382F",
        **identity,
    }


def get_employee_email_details(db, emp):
    details = dict(emp)

    required_fields = (
        "nombre",
        "apellido",
        "numero_empleado",
        "puesto",
        "sucursal",
    )

    if all(details.get(field) for field in required_fields):
        return details

    employee = row(
        db,
        """
        SELECT
            e.numero_empleado,
            e.puesto,
            u.nombre,
            u.apellido,
            s.nombre AS sucursal
        FROM public.empleados e
        JOIN public.usuarios u
            ON u.id = e.usuario_id
        JOIN public.sucursales s
            ON s.id = e.sucursal_id
        WHERE e.id = :id
        """,
        id=emp["empleado_id"],
    )

    if employee:
        for key, value in employee.items():
            if not details.get(key):
                details[key] = value

    return details


def queue(
    db,
    emp,
    kind,
    subject,
    paragraphs,
    *,
    url=None,
    brand=None,
):
    identity = (
        dict(brand)
        if brand
        else get_email_brand(db)
    )

    employee = get_employee_email_details(db, emp)

    # El correo de aprobación también puede
    # incluir un acceso directo al portal.
    if kind == "aprobacion" and not url:
        url = portal()

    rendered = render_email(
        kind=kind,
        emp=employee,
        subject=subject,
        paragraphs=paragraphs,
        url=url,
        brand=identity,
    )

    payload = {
        "to": [employee["email"]],
        "subject": subject,
        "html": rendered["html"],
        "text": rendered["text"],
        "from": settings.correo_remitente,
    }

    body = cipher().encrypt(
        json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8")
    )

    execute(
        db,
        """
        INSERT INTO gestion_interna.correo(
            clave,
            empleado_id,
            tipo,
            contenido
        )
        VALUES(
            :key,
            :id,
            :kind,
            :body
        )
        ON CONFLICT (empleado_id)
        WHERE tipo = 'bienvenida'
        DO NOTHING
        """,
        key=uuid.uuid4(),
        id=employee["empleado_id"],
        kind=kind,
        body=body,
    )


def dispatch_one(db):
    if (
        not settings.resend_api_key
        or not settings.correo_remitente
    ):
        raise RuntimeError(
            "Falta configurar el transporte Resend"
        )

    mail = row(
        db,
        """
        SELECT *,
            now() >= creado + interval '23 hours'
                AS conciliar
        FROM gestion_interna.correo
        WHERE estado = 'LISTO'
            AND proximo <= now()
        ORDER BY creado
        LIMIT 1
        FOR UPDATE SKIP LOCKED
        """,
    )

    if not mail:
        return False

    state = "CONCILIAR"
    result = None
    error = None

    if not mail["conciliar"]:
        payload = json.loads(
            cipher().decrypt(
                bytes(mail["contenido"])
            )
        )

        try:
            resp = httpx.post(
                "https://api.resend.com/emails",
                json={
                    **payload,
                    "from": (
                        payload.get("from")
                        or settings.correo_remitente
                    ),
                },
                headers={
                    "Authorization": (
                        "Bearer "
                        + settings.resend_api_key
                    ),
                    "Idempotency-Key": str(
                        mail["clave"]
                    ),
                },
                timeout=10,
            )

            if resp.is_success:
                try:
                    provider_id = resp.json()["id"]

                    if (
                        not isinstance(provider_id, str)
                        or not provider_id.strip()
                    ):
                        raise ValueError(
                            "Falta identificador del proveedor"
                        )

                    result = provider_id
                    state = "ENVIADO"

                except (KeyError, TypeError, ValueError):
                    error = "respuesta_sin_identificador"

            else:
                error = str(resp.status_code)

                state = (
                    "LISTO"
                    if (
                        resp.status_code in (429, 408)
                        or resp.status_code >= 500
                    )
                    else "REVISAR"
                )

        except httpx.TransportError:
            state = "LISTO"
            error = "transporte"

    execute(
        db,
        """
        UPDATE gestion_interna.correo
        SET
            estado = :state,
            intentos = intentos + 1,
            error = :error,
            proveedor_id = :result,
            proximo = now() + least(
                interval '1 hour',
                interval '1 minute' * (intentos + 1)
            ),
            contenido = CASE
                WHEN :state = 'ENVIADO' THEN NULL
                ELSE contenido
            END
        WHERE clave = :key
        """,
        state=state,
        error=error,
        result=result,
        key=mail["clave"],
    )

    db.commit()

    return True
