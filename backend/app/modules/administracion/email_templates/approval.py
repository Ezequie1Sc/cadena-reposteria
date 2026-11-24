
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
    name = emp.get("nombre") or "integrante del equipo"

    content = (
        status_badge("approved")
        + section_label("Resolución administrativa")
        + heading("Tu solicitud ha sido aprobada.")
        + paragraph(f"Hola, {name}.")
        + paragraph(
            "Nos complace informarte que tu proceso "
            "de incorporación ha sido aprobado por "
            "el departamento administrativo."
        )
        + notice(
            "Cuenta activa",
            "Ya puedes iniciar sesión en el portal "
            "corporativo utilizando tu correo electrónico "
            "y la contraseña que configuraste.",
            "approved",
        )
        + employee_details(emp)
        + button(
            "Acceder al portal",
            url,
            brand.get("color"),
        )
        + paragraph(
            "Gracias por formar parte de nuestro equipo. "
            "Te deseamos mucho éxito en esta nueva etapa."
        )
        + security_notice()
    )

    return render_base(
        subject=subject,
        content=content,
        preheader="Tu cuenta ha sido aprobada y activada.",
        brand=brand,
    )
