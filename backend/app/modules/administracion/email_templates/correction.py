
from .base import render_base
from .components import (
    button,
    employee_details,
    heading,
    notice,
    paragraph,
    section_label,
    status_badge,
)


def render(emp, subject, paragraphs, *, url=None, brand=None):
    brand = brand or {}
    name = emp.get("nombre") or "integrante del equipo"

    details = list(paragraphs or [])

    reason = (
        details[1]
        if len(details) > 1 and details[1]
        else "Contacta al departamento administrativo "
             "para conocer las observaciones."
    )

    action = (
        button(
            "Actualizar mi información",
            url,
            brand.get("color"),
        )
        if url
        else paragraph(
            "Utiliza el enlace de la nueva invitación "
            "de incorporación que recibirás por separado."
        )
    )

    content = (
        status_badge("correction")
        + section_label("Revisión administrativa")
        + heading("Necesitamos actualizar tu información.")
        + paragraph(f"Hola, {name}.")
        + paragraph(
            "Durante la revisión de tu solicitud, "
            "el departamento administrativo identificó "
            "información que necesita ser corregida."
        )
        + employee_details(emp)
        + notice(
            "Observaciones del administrador",
            reason,
            "correction",
        )
        + section_label("Siguiente paso")
        + paragraph(
            "Revisa las observaciones y completa nuevamente "
            "el proceso de incorporación con la información correcta."
        )
        + action
        + paragraph(
            "Tu cuenta permanecerá pendiente de activación "
            "hasta que se apruebe la información actualizada."
        )
    )

    return render_base(
        subject=subject,
        content=content,
        preheader="Tu solicitud requiere una actualización.",
        brand=brand,
    )
