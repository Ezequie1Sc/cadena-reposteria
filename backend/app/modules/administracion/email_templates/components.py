
import re
from html import escape
from urllib.parse import urlsplit

from .assets import status_image_url


# ============================================================
# IDENTIDAD VISUAL
# ============================================================

PALETTE = {
    "primary": "#49382F",
    "background": "#F5F3EF",
    "surface": "#FFFFFF",
    "text": "#292623",
    "muted": "#6C6660",
    "border": "#E8E3DD",
    "subtle": "#817B73",
}


STATUS_COLORS = {
    "invitation": {
        "color": "#525D69",
        "background": "#F0F2F4",
        "label": "Invitación de incorporación",
    },
    "verification": {
        "color": "#525D69",
        "background": "#F0F2F4",
        "label": "Verificación requerida",
    },
    "pending": {
        "color": "#806A40",
        "background": "#F6F2E9",
        "label": "Pendiente de aprobación",
    },
    "approved": {
        "color": "#52705B",
        "background": "#EEF3EF",
        "label": "Solicitud aprobada",
    },
    "welcome": {
        "color": "#52705B",
        "background": "#EEF3EF",
        "label": "Incorporación completada",
    },
    "correction": {
        "color": "#95613E",
        "background": "#F7F0EA",
        "label": "Corrección requerida",
    },
    "rejected": {
        "color": "#A35D5D",
        "background": "#F7EEEE",
        "label": "Solicitud no aprobada",
    },
}


# ============================================================
# SEGURIDAD
# ============================================================

def safe_text(value):
    """Escapa contenido dinámico antes de insertarlo en HTML."""

    return escape(
        str(value if value is not None else ""),
        quote=True,
    )


def safe_color(value, default=PALETTE["primary"]):
    """Acepta únicamente colores hexadecimales válidos."""

    if isinstance(value, str) and re.fullmatch(
        r"#[0-9a-fA-F]{6}",
        value,
    ):
        return value

    return default


def safe_url(value):
    """Permite únicamente enlaces HTTPS válidos."""

    if not value:
        return None

    try:
        value = str(value)

        if any(
            char.isspace()
            or ord(char) < 32
            or ord(char) == 127
            for char in value
        ):
            return None

        if "\\" in value:
            return None

        parsed = urlsplit(value)

        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            return None

        # Valida también el puerto, si existe.
        _ = parsed.port

        return value

    except (ValueError, TypeError):
        return None


# ============================================================
# COMPONENTES TIPOGRÁFICOS
# ============================================================

def paragraph(value):
    return f"""
    <p style="
        margin:0 0 16px;
        font-size:15px;
        line-height:1.75;
        color:{PALETTE['muted']};
    ">
        {safe_text(value)}
    </p>
    """


def heading(value):
    return f"""
    <h1 style="
        margin:0 0 24px;
        font-size:28px;
        line-height:1.3;
        font-weight:700;
        letter-spacing:-0.7px;
        color:{PALETTE['primary']};
        text-align:center;
    ">
        {safe_text(value)}
    </h1>
    """


def section_label(value):
    return f"""
    <p style="
        margin:0 0 12px;
        font-size:11px;
        line-height:1.5;
        font-weight:600;
        letter-spacing:1.2px;
        text-transform:uppercase;
        color:{PALETTE['subtle']};
    ">
        {safe_text(value)}
    </p>
    """


def divider():
    return f"""
    <table role="presentation"
        width="100%"
        cellspacing="0"
        cellpadding="0"
        border="0">
        <tr>
            <td style="padding:24px 0;">
                <div style="
                    height:1px;
                    background-color:{PALETTE['border']};
                    font-size:1px;
                    line-height:1px;
                ">&nbsp;</div>
            </td>
        </tr>
    </table>
    """


# ============================================================
# IMAGEN PRINCIPAL DEL ESTADO
# ============================================================

def status_badge(status, label=None):
    config = STATUS_COLORS.get(
        status,
        STATUS_COLORS["invitation"],
    )

    image_url = safe_url(status_image_url(status))

    status_label = safe_text(
        label or config["label"]
    )

    image_html = ""

    if image_url:
        image_html = f"""
        <tr>
            <td align="center"
                style="padding:0 0 18px;">

                <img
                    src="{safe_text(image_url)}"
                    alt=""
                    width="88"
                    height="88"
                    style="
                        display:block;
                        width:88px;
                        height:88px;
                        object-fit:contain;
                        border:0;
                        outline:none;
                        margin:0 auto;
                    "
                >

            </td>
        </tr>
        """

    return f"""
    <table role="presentation"
        width="100%"
        cellspacing="0"
        cellpadding="0"
        border="0">

        {image_html}

        <tr>
            <td align="center"
                style="padding:0 0 24px;">

                <table role="presentation"
                    cellspacing="0"
                    cellpadding="0"
                    border="0">

                    <tr>
                        <td style="
                            padding:8px 15px;
                            border-radius:6px;
                            background-color:{config['background']};
                            color:{config['color']};
                            font-size:11px;
                            font-weight:700;
                            line-height:1.5;
                            letter-spacing:0.7px;
                            text-transform:uppercase;
                        ">
                            {status_label}
                        </td>
                    </tr>

                </table>

            </td>
        </tr>

    </table>
    """


# ============================================================
# BOTÓN PRINCIPAL
# ============================================================

def button(label, url, color=None):
    validated_url = safe_url(url)

    if not validated_url:
        return ""

    color = safe_color(color)

    return f"""
    <table role="presentation"
        width="100%"
        cellspacing="0"
        cellpadding="0"
        border="0"
        style="margin:26px 0;">

        <tr>
            <td
                align="center"
                bgcolor="{color}"
                style="
                    border-radius:7px;
                    text-align:center;
                    mso-padding-alt:16px 24px;
                "
            >

                <a
                    href="{safe_text(validated_url)}"
                    target="_blank"
                    rel="noopener noreferrer"
                    style="
                        display:block;
                        padding:16px 24px;
                        border-radius:7px;
                        color:#FFFFFF;
                        font-size:14px;
                        font-weight:600;
                        text-decoration:none;
                        line-height:1.5;
                    "
                >
                    {safe_text(label)}
                </a>

            </td>
        </tr>

    </table>
    """


# ============================================================
# TARJETAS INFORMATIVAS
# ============================================================

def information_card(items, title="Información"):
    valid_items = [
        (label, value)
        for label, value in items
        if value is not None and str(value).strip()
    ]

    if not valid_items:
        return ""

    rows = []

    for index, (label, value) in enumerate(valid_items):
        border = (
            f"1px solid {PALETTE['border']}"
            if index < len(valid_items) - 1
            else "0"
        )

        rows.append(f"""
        <tr>
            <td style="
                padding:12px 0;
                border-bottom:{border};
                color:{PALETTE['muted']};
                font-size:13px;
                vertical-align:top;
            ">
                {safe_text(label)}
            </td>

            <td align="right" style="
                padding:12px 0 12px 12px;
                border-bottom:{border};
                color:{PALETTE['primary']};
                font-size:13px;
                font-weight:600;
                overflow-wrap:anywhere;
                vertical-align:top;
            ">
                {safe_text(value)}
            </td>
        </tr>
        """)

    return f"""
    <table role="presentation"
        width="100%"
        cellspacing="0"
        cellpadding="0"
        border="0"
        style="margin:24px 0;">

        <tr>
            <td style="
                padding:22px;
                background-color:{PALETTE['background']};
                border:1px solid {PALETTE['border']};
                border-radius:8px;
            ">

                {section_label(title)}

                <table role="presentation"
                    width="100%"
                    cellspacing="0"
                    cellpadding="0"
                    border="0">

                    {''.join(rows)}

                </table>

            </td>
        </tr>

    </table>
    """


# ============================================================
# AVISOS Y NOTIFICACIONES
# ============================================================

def notice(title, message, status=None):
    config = STATUS_COLORS.get(status, {})

    background = config.get(
        "background",
        PALETTE["background"],
    )

    color = config.get(
        "color",
        PALETTE["primary"],
    )

    return f"""
    <table role="presentation"
        width="100%"
        cellspacing="0"
        cellpadding="0"
        border="0"
        style="margin:22px 0;">

        <tr>
            <td style="
                padding:19px;
                background-color:{background};
                border-left:3px solid {color};
                border-radius:5px;
            ">

                <p style="
                    margin:0 0 7px;
                    font-size:13px;
                    font-weight:700;
                    color:{color};
                ">
                    {safe_text(title)}
                </p>

                <p style="
                    margin:0;
                    font-size:13px;
                    line-height:1.75;
                    color:{PALETTE['muted']};
                ">
                    {safe_text(message)}
                </p>

            </td>
        </tr>

    </table>
    """


# ============================================================
# CÓDIGO DE VERIFICACIÓN
# ============================================================

def verification_code(code):
    code = str(code)

    if not re.fullmatch(r"[0-9]{6}", code):
        raise ValueError(
            "El código debe contener seis dígitos"
        )

    return f"""
    <table role="presentation"
        width="100%"
        cellspacing="0"
        cellpadding="0"
        border="0"
        style="margin:28px 0;">

        <tr>
            <td align="center" style="
                padding:28px 16px;
                background-color:{PALETTE['background']};
                border:1px solid {PALETTE['border']};
                border-radius:8px;
            ">

                {section_label("Código de verificación")}

                <div style="
                    font-family:Consolas,Monaco,'Courier New',monospace;
                    font-size:38px;
                    font-weight:700;
                    letter-spacing:7px;
                    line-height:1.4;
                    color:{PALETTE['primary']};
                    user-select:all;
                    -webkit-user-select:all;
                    cursor:text;
                "><p>{safe_text(code)}</p></div>

                <p style="
                    margin:0;
                    font-size:12px;
                    line-height:1.6;
                    color:{PALETTE['muted']};
                ">
                    Selecciona y copia el código.
                </p>

            </td>
        </tr>

    </table>
    """


# ============================================================
# INFORMACIÓN DEL EMPLEADO
# ============================================================

def employee_details(emp):
    full_name = " ".join(
        str(emp.get(field) or "").strip()
        for field in ("nombre", "apellido")
    ).strip()

    return information_card(
        [
            ("Empleado", full_name),
            ("Matrícula", emp.get("numero_empleado")),
            ("Puesto", emp.get("puesto")),
            ("Sucursal", emp.get("sucursal")),
        ],
        title="Información laboral",
    )


# ============================================================
# SEGURIDAD DEL CORREO
# ============================================================

def security_notice(message=None):
    return notice(
        "Información de seguridad",
        message or (
            "Este correo es personal. No compartas tus "
            "credenciales ni tus enlaces de acceso con "
            "otras personas."
        ),
    )
