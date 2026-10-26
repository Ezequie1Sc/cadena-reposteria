"""Alias de compatibilidad para la tabla de usuarios.

Permite que los módulos existentes de clientes y empleados
continúen utilizando users_reference.c.id.

La definición completa de la tabla usuarios pertenece
al modelo User.
"""

from app.modules.users.model import User


users_reference = User.__table__