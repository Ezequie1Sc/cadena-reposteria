
from html.parser import HTMLParser

from . import (
    invitation,
    verification,
    application,
    approval,
    welcome,
    correction,
    rejection,
)

from .components import safe_url


TEMPLATES = {
    "invitacion": invitation.render,
    "codigo": verification.render,
    "solicitud": application.render,
    "aprobacion": approval.render,
    "bienvenida": welcome.render,
    "correccion": correction.render,
    "rechazar": rejection.render,
}


class PlainTextParser(HTMLParser):
    BLOCK_TAGS = {
        "p",
        "h1",
        "h2",
        "h3",
        "div",
        "tr",
        "table",
        "br",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.ignored = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"head", "style", "script"}:
            self.ignored += 1
            return

        if self.ignored:
            return

        if tag in self.BLOCK_TAGS:
            self.parts.append("\n")

        if tag == "td":
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in {"head", "style", "script"}:
            self.ignored = max(0, self.ignored - 1)
            return

        if not self.ignored and tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.ignored:
            self.parts.append(data)

    def get_text(self):
        lines = []

        for line in "".join(self.parts).splitlines():
            cleaned = " ".join(line.split())

            if cleaned:
                lines.append(cleaned)

        return "\n\n".join(lines)


def render_email(
    kind,
    emp,
    subject,
    paragraphs,
    *,
    url=None,
    brand=None,
):
    template = TEMPLATES.get(kind)

    if template is None:
        raise ValueError(
            f"No existe una plantilla para el tipo: {kind}"
        )

    validated_url = safe_url(url)

    if url and not validated_url:
        raise ValueError("El enlace del correo no es válido")

    html = template(
        emp=emp,
        subject=subject,
        paragraphs=list(paragraphs or []),
        url=validated_url,
        brand=brand or {},
    )

    parser = PlainTextParser()
    parser.feed(html)
    parser.close()

    text = parser.get_text()

    if validated_url:
        text += (
            "\n\nEnlace de acceso al portal:\n"
            + validated_url
        )

    return {
        "html": html,
        "text": text,
    }


__all__ = ["render_email"]
