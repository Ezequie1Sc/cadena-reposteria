
from .base import render_base
from .components import (
    employee_details,
    heading,
    notice,
    paragraph,
    section_label,
    status_badge,
)


def render(emp, subject, paragraphs, *, url=None, brand=None):
    name = emp.get("nombre")

    greeting = paragraph(f"Hola, {name}.") if name else ""

    content = (
        status_badge("pending")
        + section_label("Proceso de incorporación")
        + heading("Hemos recibido tu solicitud.")
        + greeting
        + paragraph(
            "Tu información ha sido registrada correctamente "
            "y se encuentra disponible para su revisión "
            "por parte del departamento administrativo."
        )
        + employee_details(emp)
        + notice(
            "Pendiente de aprobación",
            "Tu cuenta todavía no está activa. Recibirás "
            "una notificación cuando el equipo administrativo "
            "apruebe tu solicitud o requiera información adicional.",
            "pending",
        )
        + paragraph(
            "Por el momento no necesitas realizar ninguna "
            "acción adicional."
        )
        + paragraph(
            "Gracias por completar tu proceso de registro."
        )
    )

    return render_base(
        subject=subject,
        content=content,
        preheader="Tu solicitud está pendiente de revisión.",
        brand=brand,
    )
