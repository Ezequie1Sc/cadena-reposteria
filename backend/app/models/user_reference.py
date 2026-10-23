
"""Referencia a la tabla existente de usuarios.

Permite resolver la clave foránea clientes.usuario_id
sin implementar todavía el modelo completo de usuarios.
"""

from sqlalchemy import BigInteger, Column, Table

from app.db.session import Base


users_reference = Table(
    "usuarios",
    Base.metadata,
    Column(
        "id",
        BigInteger,
        primary_key=True,
    ),
    info={"reference_only": True},
)
