
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
    name = emp.get("nombre") or "solicitante"

    details = list(paragraphs or [])

    reason = (
        details[1]
        if len(details) > 1 and details[1]
        else "Contacta al departamento administrativo "
             "para obtener más información."
    )

    content = (
        status_badge("rejected")
        + section_label("Resolución administrativa")
        + heading("Tu solicitud no ha sido aprobada.")
        + paragraph(f"Hola, {name}.")
        + paragraph(
            "El departamento administrativo ha concluido "
            "la revisión de tu solicitud de incorporación."
        )
        + paragraph(
            "Por el momento, no ha sido posible aprobar "
            "tu solicitud ni activar tu cuenta."
        )
        + employee_details(emp)
        + notice(
            "Motivo de la resolución",
            reason,
            "rejected",
        )
        + paragraph(
            "Si necesitas información adicional sobre esta "
            "decisión, puedes comunicarte con el "
            "departamento administrativo."
        )
        + paragraph(
            "Agradecemos tu tiempo y comprensión."
        )
    )

    return render_base(
        subject=subject,
        content=content,
        preheader="Consulta la resolución de tu solicitud.",
        brand=brand,
    )
