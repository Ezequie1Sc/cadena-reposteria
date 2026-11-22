import json
import uuid
from html import escape
from urllib.parse import urlsplit

import httpx
from cryptography.fernet import Fernet
from fastapi import HTTPException

from app.core.config import settings

from .common import execute, row


def cipher():
    if not settings.correo_clave_cifrado:
        raise HTTPException(503, "Falta configurar el cifrado de correo")
    return Fernet(settings.correo_clave_cifrado.encode())


def portal():
    url = (settings.portal_url or "").rstrip("/")
    if urlsplit(url).scheme != "https" or not urlsplit(url).hostname:
        raise HTTPException(503, "Configura la URL HTTPS del portal")
    return url


def queue(db, emp, kind, subject, paragraphs, *, url=None, brand=None):
    brand = brand or {}
    html = '<html lang="es"><body style="font-family:Arial;color:#292320">'
    if brand.get("logotipo"):
        html += (
            '<img width="96" alt="" src="'
            + escape(str(brand["logotipo"]), quote=True)
            + '">'
        )
    html += (
        '<h1 style="color:'
        + escape(brand.get("color", "#49382f"))
        + '">'
        + escape(subject)
        + "</h1>"
    )
    html += "".join("<p>" + escape(str(p)) + "</p>" for p in paragraphs if p)
    if url:
        html += '<p><a href="' + escape(url, quote=True) + '">Acceder al portal</a></p>'
    html += "</body></html>"
    body = cipher().encrypt(
        json.dumps(
            {
                "to": [emp["email"]],
                "subject": subject,
                "html": html,
                "from": settings.correo_remitente,
            }
        ).encode()
    )
    execute(
        db,
        """INSERT INTO gestion_interna.correo(clave,empleado_id,tipo,contenido)
           VALUES(:key,:id,:kind,:body) ON CONFLICT (empleado_id) WHERE tipo='bienvenida' DO NOTHING""",
        key=uuid.uuid4(),
        id=emp["empleado_id"],
        kind=kind,
        body=body,
    )


def dispatch_one(db):
    if not settings.resend_api_key or not settings.correo_remitente:
        raise RuntimeError("Falta configurar el transporte Resend")
    mail = row(
        db,
        """SELECT *, now() >= creado + interval '23 hours' AS conciliar
        FROM gestion_interna.correo WHERE estado='LISTO' AND proximo<=now()
        ORDER BY creado LIMIT 1 FOR UPDATE SKIP LOCKED""",
    )
    if not mail:
        return False
    state, result, error = "CONCILIAR", None, None
    if not mail["conciliar"]:
        payload = json.loads(cipher().decrypt(bytes(mail["contenido"])))
        try:
            resp = httpx.post(
                "https://api.resend.com/emails",
                json={
                    **payload,
                    "from": payload.get("from") or settings.correo_remitente,
                },
                headers={
                    "Authorization": "Bearer " + settings.resend_api_key,
                    "Idempotency-Key": str(mail["clave"]),
                },
                timeout=10,
            )
            if resp.is_success:
                try:
                    provider_id = resp.json()["id"]
                    if not isinstance(provider_id, str) or not provider_id.strip():
                        raise ValueError("Falta identificador del proveedor")
                    result = provider_id
                    state = "ENVIADO"
                except (KeyError, TypeError, ValueError):
                    error = "respuesta_sin_identificador"
            else:
                error = str(resp.status_code)
                state = (
                    "LISTO"
                    if resp.status_code in (429, 408) or resp.status_code >= 500
                    else "REVISAR"
                )
        except httpx.TransportError:
            state, error = "LISTO", "transporte"
    execute(
        db,
        """UPDATE gestion_interna.correo SET estado=:state,intentos=intentos+1,error=:error,
        proveedor_id=:result,proximo=now()+least(interval '1 hour',interval '1 minute'*(intentos+1)),
        contenido=CASE WHEN :state='ENVIADO' THEN NULL ELSE contenido END WHERE clave=:key""",
        state=state,
        error=error,
        result=result,
        key=mail["clave"],
    )
    db.commit()
    return True
