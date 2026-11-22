export interface SalesGroup {
  grupo: string;
  ventas: number;
  total: string;
}
export interface ProductGroup {
  producto_id: number;
  cantidad: number;
  total: string;
}
export interface DashboardData {
  zona_horaria: string;
  productos_activos: number;
  sucursales_activas: number;
  clientes_registrados: number;
  pedidos_pendientes: number;
  ventas_dia: number;
  ingresos_mes: string;
  productos_mas_vendidos: ProductGroup[];
  alertas_inventario: number;
}
export interface CatalogEntry {
  id: number;
  nombre: string;
}
export type ReportName = 'ventas' | 'productos' | 'pagos' | 'inventarios' | 'movimientos';
export const zone = 'America/Merida';
export const formatMoney = (value: string | number) =>
  new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(Number(value));

// El día civil elegido pertenece a la zona comercial, independientemente del navegador.
// UTC se usa para sumar días de calendario, sin suponer una duración local de 24 horas.
const isoDate = new Intl.DateTimeFormat('sv-SE', {
  timeZone: zone,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
});
const localTime = new Intl.DateTimeFormat('sv-SE', {
  timeZone: zone,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hourCycle: 'h23',
});
export const currentDay = () => isoDate.format(new Date());
export function shiftDay(day: string, delta: number) {
  const date = new Date(day + 'T12:00:00Z');
  date.setUTCDate(date.getUTCDate() + delta);
  return date.toISOString().slice(0, 10);
}
export function startOfDay(day: string) {
  const midnight = Date.parse(day + 'T00:00:00Z');
  let candidate = midnight;
  for (let i = 0; i < 3; i++) {
    const civil = localTime.format(new Date(candidate)).replace(' ', 'T');
    const error = midnight - Date.parse(civil + 'Z');
    if (!error) break;
    candidate += error;
  }
  return new Date(candidate).toISOString();
}
export const reportTitles: Record<ReportName, string> = {
  ventas: 'Ventas',
  productos: 'Productos',
  pagos: 'Pagos',
  inventarios: 'Inventario',
  movimientos: 'Movimientos',
};
export const reportColumns: Record<ReportName, string[]> = {
  ventas: ['grupo', 'ventas', 'total'],
  productos: ['producto_id', 'cantidad', 'total'],
  pagos: ['metodo', 'estado', 'sucursal_id', 'pagos', 'total'],
  inventarios: ['id', 'producto_id', 'sucursal_id', 'cantidad', 'stock_minimo', 'updated_at'],
  movimientos: [
    'id',
    'inventario_id',
    'tipo',
    'cantidad',
    'motivo',
    'referencia_tipo',
    'referencia_id',
    'usuario_id',
    'created_at',
  ],
};
export const columnTitles: Record<string, string> = {
  id: 'ID',
  grupo: 'Grupo',
  ventas: 'Ventas confirmadas',
  total: 'Importe (MXN)',
  producto_id: 'Producto',
  cantidad: 'Cantidad',
  metodo: 'Método',
  estado: 'Estado',
  sucursal_id: 'Sucursal',
  pagos: 'Pagos',
  stock_minimo: 'Stock mínimo',
  updated_at: 'Actualización',
  inventario_id: 'Inventario',
  tipo: 'Movimiento',
  motivo: 'Motivo',
  referencia_tipo: 'Tipo de referencia',
  referencia_id: 'ID de referencia',
  usuario_id: 'Usuario',
  created_at: 'Fecha',
};
