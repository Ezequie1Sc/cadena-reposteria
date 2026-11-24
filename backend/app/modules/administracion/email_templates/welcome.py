
from .base import render_base
from .components import (
    button,
    divider,
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
    name = emp.get("nombre") or "integrante del equipo"

    message = brand.get("mensaje") or (
        "Nos alegra contar contigo. Esperamos que esta "
        "nueva etapa esté llena de oportunidades, "
        "aprendizaje y crecimiento profesional."
    )

    # onboarding.py proporciona:
    # Nombre, puesto, sucursal, matrícula, mensaje,
    # beneficios, firma y contacto.
    details = list(paragraphs or [])
    benefits = details[5:-2] if len(details) >= 7 else []

    benefits_html = ""

    if benefits:
        benefits_html = (
            divider()
            + section_label("Tus beneficios")
            + paragraph(
                "Estos son los beneficios que actualmente "
                "corresponden a tu perfil laboral."
            )
            + "".join(
                notice("Beneficio empresarial", benefit)
                for benefit in benefits
                if benefit
            )
        )

    content = (
        status_badge("welcome")
        + section_label("Bienvenida empresarial")
        + heading(f"Bienvenido al equipo de {company}.")
        + paragraph(f"Hola, {name}.")
        + paragraph(message)
        + employee_details(emp)
        + benefits_html
        + divider()
        + section_label("Tu espacio de trabajo")
        + paragraph(
            "Desde el portal corporativo podrás acceder "
            "a las herramientas y funciones asignadas "
            "a tu perfil de empleado."
        )
        + button(
            "Entrar al portal",
            url,
            brand.get("color"),
        )
        + notice(
            "Incorporación completada",
            "Tu cuenta se encuentra activa y lista para utilizarse.",
            "welcome",
        )
        + security_notice()
    )

    return render_base(
        subject=subject,
        content=content,
        preheader=f"Te damos la bienvenida a {company}.",
        brand=brand,
    )
