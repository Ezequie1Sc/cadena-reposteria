from datetime import datetime
from decimal import Decimal
from app.shared.commerce import ORMModel
from app.modules.sales.schemas import SaleResponse
from app.modules.payments.schemas import PaymentResponse


class TicketResponse(ORMModel):
    id: int
    numero_ticket: str
    fecha_emision: datetime
    venta: SaleResponse
    sucursal_nombre: str
    pagos: list[PaymentResponse]
    metodos: dict[int, str]
    pagado: bool
    impuestos_desglosados: Decimal | None = None
    aviso: str = "Comprobante comercial. No es CFDI. Impuestos no desglosados."
