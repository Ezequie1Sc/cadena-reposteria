
from .base import render_base
from .components import (
    heading,
    notice,
    paragraph,
    section_label,
    security_notice,
    status_badge,
    verification_code,
)


def render(emp, subject, paragraphs, *, url=None, brand=None):
    if not paragraphs:
        raise ValueError("No se proporcionó el código de verificación")

    code = str(paragraphs[0])

    content = (
        status_badge("verification")
        + section_label("Seguridad e identidad digital")
        + heading("Verifica tu correo electrónico.")
        + paragraph(
            "Para proteger tu cuenta y continuar con tu "
            "incorporación, necesitamos confirmar que "
            "este correo electrónico te pertenece."
        )
        + paragraph(
            "Introduce el siguiente código en el portal "
            "corporativo."
        )
        + verification_code(code)
        + notice(
            "Vigencia del código",
            "El código estará disponible durante 10 minutos "
            "desde su emisión.",
            "pending",
        )
        + security_notice(
            "Nunca compartas este código con otras personas. "
            "El equipo administrativo no te solicitará "
            "este código por teléfono ni por mensaje. "
            "Si no solicitaste esta verificación, "
            "puedes ignorar este correo."
        )
    )

    return render_base(
        subject=subject,
        content=content,
        preheader="Confirma tu identidad para continuar.",
        brand=brand,
        department="Seguridad e identidad digital",
    )
