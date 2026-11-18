from decimal import Decimal
from app.shared.commerce import ORMModel


class SalesAggregate(ORMModel):
    grupo: str
    ventas: int
    total: Decimal


class ProductAggregate(ORMModel):
    producto_id: int
    cantidad: int
    total: Decimal


class PaymentAggregate(ORMModel):
    estado: str
    metodo: str
    sucursal_id: int
    pagos: int
    total: Decimal


class Dashboard(ORMModel):
    zona_horaria: str
    productos_activos: int
    sucursales_activas: int
    clientes_registrados: int
    pedidos_pendientes: int
    ventas_dia: int
    ingresos_mes: Decimal
    productos_mas_vendidos: list[ProductAggregate]
    alertas_inventario: int
