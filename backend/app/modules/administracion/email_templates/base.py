
from datetime import datetime, timezone

from .assets import logo_url

from .components import (
    PALETTE,
    safe_color,
    safe_text,
    safe_url,
)


def render_base(
    *,
    subject,
    content,
    preheader="",
    brand=None,
    department="Departamento de Administración",
):
    brand = brand or {}

    company_name = safe_text(
        brand.get("nombre") or "DulceGestión"
    )

    primary = safe_color(brand.get("color"))

    corporate_logo = safe_url(
        brand.get("logotipo")
    ) or logo_url()

    signature = safe_text(
        brand.get("firma") or department
    )

    contact = safe_text(
        brand.get("contacto") or ""
    )

    year = datetime.now(timezone.utc).year

    contact_html = ""

    if contact:
        contact_html = f"""
        <p style="
            margin:8px 0 0;
            font-size:12px;
            line-height:1.7;
            color:{PALETTE['muted']};
        ">
            {contact}
        </p>
        """

    return f"""<!DOCTYPE html>
<html lang="es">

<head>

    <meta charset="UTF-8">

    <meta
        http-equiv="Content-Type"
        content="text/html; charset=UTF-8"
    >

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <meta name="color-scheme" content="light">

    <meta name="supported-color-schemes" content="light">

    <title>{safe_text(subject)}</title>

    <style>

        body {{
            margin:0;
            padding:0;
            width:100%;
            background-color:{PALETTE['background']};
            -webkit-text-size-adjust:100%;
            -ms-text-size-adjust:100%;
        }}

        table {{
            border-collapse:separate;
            border-spacing:0;
        }}

        img {{
            border:0;
            outline:none;
            text-decoration:none;
        }}

        @media only screen and (max-width:600px) {{

            .outer-padding {{
                padding:16px 10px !important;
            }}

            .email-container {{
                width:100% !important;
            }}

            .email-header {{
                padding:24px 18px !important;
            }}

            .email-content {{
                padding:28px 22px !important;
            }}

            .email-footer {{
                padding:24px 22px !important;
            }}

            .corporate-logo {{
                width:230px !important;
                max-width:100% !important;
                height:auto !important;
            }}

            h1 {{
                font-size:24px !important;
            }}

        }}

    </style>

</head>

<body style="
    margin:0;
    padding:0;
    background-color:{PALETTE['background']};
    font-family:Arial,Helvetica,sans-serif;
    color:{PALETTE['text']};
">

    <!-- TEXTO DE VISTA PREVIA -->

    <div style="
        display:none;
        max-height:0;
        max-width:0;
        overflow:hidden;
        opacity:0;
        font-size:1px;
        line-height:1px;
        mso-hide:all;
    ">
        {safe_text(preheader or subject)}
    </div>


    <!-- CONTENEDOR PRINCIPAL -->

    <table
        role="presentation"
        width="100%"
        cellspacing="0"
        cellpadding="0"
        border="0"
        bgcolor="{PALETTE['background']}"
    >

        <tr>

            <td
                align="center"
                class="outer-padding"
                style="padding:40px 16px;"
            >

                <!--[if mso]>
                <table role="presentation"
                    width="600"
                    cellspacing="0"
                    cellpadding="0"
                    border="0">
                    <tr><td>
                <![endif]-->

                <table
                    role="presentation"
                    width="100%"
                    cellspacing="0"
                    cellpadding="0"
                    border="0"
                    class="email-container"
                    style="
                        max-width:600px;
                        background-color:#FFFFFF;
                        border:1px solid {PALETTE['border']};
                        border-radius:10px;
                    "
                >

                    <!-- ACENTO CORPORATIVO -->

                    <tr>
                        <td
                            bgcolor="{primary}"
                            height="5"
                            style="
                                height:5px;
                                font-size:1px;
                                line-height:5px;
                                border-radius:10px 10px 0 0;
                            "
                        >&nbsp;</td>
                    </tr>


                    <!-- LOGO CORPORATIVO -->

                    <tr>

                        <td
                            align="center"
                            class="email-header"
                            style="
                                padding:28px 40px;
                                background-color:#FFFFFF;
                                border-bottom:1px solid
                                    {PALETTE['border']};
                            "
                        >

                            <img
                                src="{safe_text(corporate_logo)}"
                                alt="{company_name}"
                                width="280"
                                class="corporate-logo"
                                style="
                                    display:block;
                                    width:280px;
                                    max-width:100%;
                                    height:auto;
                                    border:0;
                                    margin:0 auto;
                                "
                            >

                            <p style="
                                margin:16px 0 0;
                                font-size:10px;
                                font-weight:600;
                                letter-spacing:2px;
                                color:{PALETTE['subtle']};
                                text-transform:uppercase;
                            ">
                                Portal corporativo
                            </p>

                        </td>

                    </tr>


                    <!-- CONTENIDO DINÁMICO -->

                    <tr>

                        <td
                            class="email-content"
                            style="
                                padding:36px 40px;
                                font-size:15px;
                                line-height:1.7;
                            "
                        >

                            {content}

                        </td>

                    </tr>


                    <!-- PIE CORPORATIVO -->

                    <tr>

                        <td
                            class="email-footer"
                            style="
                                padding:26px 40px;
                                border-top:1px solid
                                    {PALETTE['border']};
                                background-color:#FAF9F7;
                                border-radius:0 0 10px 10px;
                            "
                        >

                            <p style="
                                margin:0;
                                font-size:13px;
                                font-weight:700;
                                color:{primary};
                            ">
                                {signature}
                            </p>

                            {contact_html}

                            <p style="
                                margin:14px 0 0;
                                font-size:11px;
                                line-height:1.75;
                                color:{PALETTE['muted']};
                            ">
                                Este mensaje fue generado
                                automáticamente por el portal
                                corporativo de {company_name}.
                            </p>

                            <p style="
                                margin:8px 0 0;
                                font-size:11px;
                                line-height:1.75;
                                color:{PALETTE['subtle']};
                            ">
                                Si necesitas asistencia,
                                comunícate con el departamento
                                administrativo.
                            </p>

                        </td>

                    </tr>

                </table>

                <!--[if mso]>
                    </td></tr>
                </table>
                <![endif]-->


                <!-- DERECHOS RESERVADOS -->

                <table
                    role="presentation"
                    width="100%"
                    cellspacing="0"
                    cellpadding="0"
                    border="0"
                    style="max-width:600px;"
                >

                    <tr>

                        <td
                            align="center"
                            style="padding:24px 12px 0;"
                        >

                            <p style="
                                margin:0 0 6px;
                                font-size:12px;
                                font-weight:600;
                                color:{PALETTE['primary']};
                            ">
                                {company_name}
                            </p>

                            <p style="
                                margin:0;
                                font-size:11px;
                                line-height:1.7;
                                color:{PALETTE['subtle']};
                            ">
                                &copy; {year} {company_name}.
                                Todos los derechos reservados.
                            </p>

                        </td>

                    </tr>

                </table>

            </td>

        </tr>

    </table>

</body>

</html>
"""
