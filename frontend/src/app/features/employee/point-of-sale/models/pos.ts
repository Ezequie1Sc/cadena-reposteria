export interface Product {
  id: number;
  nombre: string;
  sku: string;
  precio: string;
  imagen_url: string | null;
  categoria_id: number;
  activo: boolean;
}
export interface Category {
  id: number;
  nombre: string;
  activo: boolean;
}
export interface Inventory {
  producto_id: number;
  sucursal_id: number;
  cantidad: number;
}
export interface CartLine {
  producto_id: number;
  cantidad: number;
}
export interface SaleBody {
  sucursal_id: number;
  productos: CartLine[];
  cliente_id?: number;
}
export interface Sale {
  id: number;
  numero_venta: string;
  total: string;
  subtotal: string;
  estado: 'PENDIENTE' | 'CONFIRMADA' | 'CANCELADA';
  vence_at: string | null;
  detalles: {
    producto_id: number;
    producto_nombre: string | null;
    cantidad: number;
    precio_unitario: string;
    subtotal: string;
  }[];
}
export type MethodCode = 'EFECTIVO' | 'TARJETA' | 'SPEI' | 'DEPOSITO';
export interface Method {
  id: number;
  codigo: MethodCode;
  nombre: string;
}
export interface PaymentBody {
  venta_id: number;
  metodo: MethodCode;
  monto: string;
  referencia?: string;
}
export interface Payment {
  id: number;
  venta_id: number;
  metodo_pago_id: number;
  monto: string;
  estado: string;
  proveedor: string;
}
export interface Ticket {
  id: number;
  numero_ticket: string;
  pagado: boolean;
}
export interface Intent<T> {
  key: string;
  body: T;
}
export interface Checkout {
  saleIntent?: Intent<SaleBody>;
  saleId?: number;
  paymentIntent?: Intent<PaymentBody>;
  paymentId?: number;
  ticketId?: number;
}

const peso = new Intl.NumberFormat('es-MX', { useGrouping: true, maximumFractionDigits: 0 });

/** Decimal as returned by FastAPI. Keep whole cents through multiplication and summation. */
export function cents(value: string): bigint {
  const match = /^(\d+)(?:\.(\d{1,2}))?$/.exec(String(value));
  if (!match) throw new Error('El servidor devolvió un importe con formato inválido.');
  return BigInt(match[1]) * 100n + BigInt((match[2] || '').padEnd(2, '0'));
}

export function currency(amount: bigint): string {
  return '$' + peso.format(amount / 100n) + '.' + (amount % 100n).toString().padStart(2, '0');
}

export function paymentBody(sale: Sale, method: MethodCode, reference: string): PaymentBody {
  if (sale.estado !== 'PENDIENTE') throw new Error('La venta ya no admite un cobro.');
  const result: PaymentBody = { venta_id: sale.id, metodo: method, monto: sale.total };
  if (method !== 'EFECTIVO') {
    const trimmed = reference.trim();
    if (trimmed.length < 3 || trimmed.length > 255)
      throw new Error('Escribe una referencia de 3 a 255 caracteres.');
    result.referencia = trimmed;
  }
  return result;
}

export function stockProblem(
  lines: CartLine[],
  stock: Map<number, number>,
  products: Product[],
): string | undefined {
  if (lines.length === 0) return 'Agrega al menos un producto.';
  if (lines.length > 100) return 'La venta admite hasta 100 productos distintos.';
  for (const line of lines) {
    const product = products.find((p) => p.id === line.producto_id && p.activo);
    if (!product) return 'Un producto dejó de estar activo. Retíralo del carrito.';
    const available = stock.get(product.id) ?? 0;
    if (!Number.isSafeInteger(line.cantidad) || line.cantidad < 1 || line.cantidad > available)
      return product.nombre + ' tiene ' + available + ' unidades disponibles.';
  }
  return undefined;
}
