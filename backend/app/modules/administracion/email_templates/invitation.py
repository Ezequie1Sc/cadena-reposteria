
from .base import render_base
from .components import (
    button,
    employee_details,
    heading,
    notice,
    paragraph,
    section_label,
    security_notice,
    status_badge,
)


def render(emp, subject, paragraphs, *, url=None, brand=None):
    brand = brand or {}
    company = brand.get("nombre") or "DulceGestión"
    name = emp.get("nombre") or "nuevo integrante"

    content = (
        status_badge("invitation")
        + section_label("Incorporación de personal")
        + heading("Te damos la bienvenida al equipo.")
        + paragraph(f"Hola, {name}.")
        + paragraph(
            f"Has sido invitado a formar parte de {company}. "
            "Para comenzar, necesitamos que completes "
            "tu proceso de incorporación al portal corporativo."
        )
        + employee_details(emp)
        + section_label("Siguiente paso")
        + paragraph(
            "Accede al portal, verifica tu correo electrónico "
            "y establece una contraseña segura para tu cuenta."
        )
        + button(
            "Completar mi incorporación",
            url,
            brand.get("color"),
        )
        + notice(
            "Vigencia de la invitación",
            "Este enlace estará disponible durante 48 horas "
            "desde su emisión.",
            "pending",
        )
        + security_notice(
            "Esta invitación es personal e intransferible. "
            "Si no esperabas recibir este correo, puedes "
            "ignorarlo o contactar al departamento administrativo."
        )
    )

    return render_base(
        subject=subject,
        content=content,
        preheader="Completa tu incorporación al equipo.",
        brand=brand,
    )
