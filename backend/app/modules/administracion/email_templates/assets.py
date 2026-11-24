
from pathlib import Path


# Directorio físico de los recursos.
STATIC_DIRECTORY = (
    Path(__file__).resolve().parents[3]
    / "static"
    / "emails"
    / "png"
)


# Dirección pública del backend en producción.
ASSETS_BASE_URL = (
    "https://cadena-reposteria.onrender.com"
    "/static/emails/png"
)


LOGO_FILENAME = "logo-dulcegestion.png"


STATUS_IMAGES = {
    "invitation": "invitacion.png",
    "verification": "verificacion.png",
    "pending": "pendiente.png",
    "approved": "aprobado.png",
    "welcome": "bienvenida.png",
    "correction": "correccion.png",
    "rejected": "rechazado.png",
}


def logo_url():
    """Devuelve la dirección pública del logo corporativo."""
    return f"{ASSETS_BASE_URL}/{LOGO_FILENAME}"


def status_image_url(status):
    """Devuelve la imagen correspondiente al estado."""
    filename = STATUS_IMAGES.get(status)

    if not filename:
        return None

    return f"{ASSETS_BASE_URL}/{filename}"


def missing_assets():
    """Identifica recursos gráficos que todavía no existen."""
    filenames = [
        LOGO_FILENAME,
        *STATUS_IMAGES.values(),
    ]

    return [
        filename
        for filename in filenames
        if not (STATIC_DIRECTORY / filename).is_file()
    ]
