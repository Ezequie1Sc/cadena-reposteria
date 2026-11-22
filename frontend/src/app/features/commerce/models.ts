export type Resource = 'ventas' | 'pedidos' | 'pagos' | 'tickets' | 'facturas';
export type Action =
  | 'crear-pedido'
  | 'pagar'
  | 'facturar'
  | 'cancelar-venta'
  | 'pedido-estado'
  | 'pago-estado'
  | 'factura-estado';
export interface Line {
  producto_id: number;
  producto_nombre?: string | null;
  producto_sku?: string | null;
  cantidad: number;
  precio_unitario: string;
  subtotal: string;
  descuento: string;
}
export interface Entry {
  id: number;
  numero_venta?: string;
  numero_ticket?: string;
  numero_pedido?: string;
  fecha?: string;
  fecha_pedido?: string;
  created_at?: string;
  fecha_emision?: string;
  estado?: string;
  venta_id?: number;
  pedido_id?: number | null;
  cliente_id?: number | null;
  empleado_id?: number | null;
  sucursal_id?: number;
  sucursal_nombre?: string;
  total?: string;
  subtotal?: string;
  descuento?: string;
  tipo?: string;
  detalles?: Line[];
  venta?: Entry;
  pagado?: boolean;
  pagos?: Entry[];
  metodos?: Record<string, string>;
  aviso?: string;
  monto?: string;
  moneda?: string;
  metodo_pago_id?: number;
  proveedor?: string;
  referencia?: string | null;
  confirmado_por?: number | null;
  paid_at?: string | null;
  vence_at?: string | null;
  notas?: string | null;
  direccion_entrega?: string | null;
  razon_social?: string;
  rfc?: string;
  uso_cfdi?: string;
  tipo_persona?: string;
  direccion_fiscal?: string;
  email_fiscal?: string;
  regimen_fiscal?: string;
  codigo_postal_fiscal?: string;
  referencia_proveedor?: string | null;
  uuid?: string | null;
}
export interface EventEntry {
  id: number;
  estado: string;
  anterior: string | null;
  motivo: string | null;
  usuario_id: number;
  created_at: string;
}
export interface Method {
  id: number;
  codigo: string;
  nombre: string;
}
export interface Option {
  id: number;
  nombre: string;
  sku?: string;
}
export const modules = {
  ventas: {
    title: 'Ventas',
    singular: 'Venta',
    description: 'Consulta importes, reservas y cobros de cada venta.',
    states: ['PENDIENTE', 'CONFIRMADA', 'CANCELADA'],
  },
  pedidos: {
    title: 'Pedidos',
    singular: 'Pedido',
    description: 'Sigue cada pedido desde la reserva hasta la entrega.',
    states: ['PENDIENTE', 'CONFIRMADO', 'PREPARANDO', 'LISTO', 'ENTREGADO', 'CANCELADO'],
  },
  pagos: {
    title: 'Pagos',
    singular: 'Pago',
    description: 'Revisa registros de cobro y verifica los pagos pendientes.',
    states: [
      'PENDIENTE',
      'EN_PROCESO',
      'APROBADO',
      'RECHAZADO',
      'CANCELADO',
      'REEMBOLSADO',
      'VENCIDO',
    ],
  },
  tickets: {
    title: 'Tickets',
    singular: 'Ticket',
    description: 'Consulta e imprime los comprobantes comerciales de venta.',
    states: [],
  },
  facturas: {
    title: 'Solicitudes de factura',
    singular: 'Solicitud',
    description: 'Consulta los datos fiscales y da seguimiento a cada solicitud.',
    states: ['PENDIENTE', 'EMITIDA', 'CANCELADA'],
  },
} satisfies Record<
  Resource,
  { title: string; singular: string; description: string; states: string[] }
>;
export const orderNext: Record<string, string | undefined> = {
  CONFIRMADO: 'PREPARANDO',
  PREPARANDO: 'LISTO',
  LISTO: 'ENTREGADO',
};
export function nameOf(row: Entry, resource: Resource): string {
  return (
    row.numero_venta ||
    row.numero_ticket ||
    row.numero_pedido ||
    modules[resource].singular + ' #' + row.id
  );
}
export function stateOf(row: Entry): string {
  return row.estado || (row.pagado ? 'PAGADO' : 'SIN PAGO CONFIRMADO');
}
export function human(value: string | null | undefined): string {
  if (!value) return '—';
  return value[0] + value.slice(1).toLocaleLowerCase('es-MX').replaceAll('_', ' ');
}
const dates = new Intl.DateTimeFormat('es-MX', { dateStyle: 'medium', timeStyle: 'short' });
export function dateLabel(value?: string | null): string {
  return value ? dates.format(new Date(value)) : '—';
}
export function amount(value?: string | null): string {
  if (!value) return '—';
  const [units, cents = ''] = String(value).split('.');
  return '$' + BigInt(units).toLocaleString('es-MX') + '.' + cents.padEnd(2, '0').slice(0, 2);
}
export function facts(row: Entry, kind: Resource): { label: string; value: string | number }[] {
  const entries: [string, string | number | null | undefined][] = [
    ['ID', row.id],
    ['Sucursal', row.sucursal_nombre ?? row.sucursal_id],
    ['Cliente', row.cliente_id],
    ['Empleado', row.empleado_id],
    ['Tipo', row.tipo],
    ['Venta', row.venta_id ?? row.venta?.numero_venta],
    ['Pedido', row.pedido_id],
    ['Subtotal', row.subtotal && amount(row.subtotal)],
    ['Descuento', row.descuento && amount(row.descuento)],
    ['Total', (row.total || row.venta?.total) && amount(row.total ?? row.venta?.total)],
    ['Importe', row.monto && amount(row.monto)],
    ['Moneda', row.moneda],
    ['Proveedor', row.proveedor],
    ['Referencia', row.referencia],
    ['Verificado por', row.confirmado_por],
    ['Verificado el', row.paid_at && dateLabel(row.paid_at)],
    ['Vencimiento', row.vence_at && dateLabel(row.vence_at)],
    ['Notas', row.notas],
    ['Dirección', row.direccion_entrega],
    ['Razón social', row.razon_social],
    ['RFC', row.rfc],
    ['Tipo de persona', row.tipo_persona],
    ['Régimen fiscal', row.regimen_fiscal],
    ['Uso de CFDI', row.uso_cfdi],
    ['CP fiscal', row.codigo_postal_fiscal],
    ['Domicilio fiscal', row.direccion_fiscal],
    ['Correo fiscal', row.email_fiscal],
    ['UUID', row.uuid],
    ['Referencia externa', row.referencia_proveedor],
    [
      'Emisión externa',
      kind === 'facturas' && row.fecha_emision ? dateLabel(row.fecha_emision) : undefined,
    ],
  ];
  return entries.flatMap(([label, value]) =>
    value == null || value === '' ? [] : [{ label, value }],
  );
}
