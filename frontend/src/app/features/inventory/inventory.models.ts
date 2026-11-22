export interface Inventory {
  id: number;
  producto_id: number;
  sucursal_id: number;
  cantidad: number;
  stock_minimo: number;
  updated_at: string;
}

export interface NamedRecord {
  id: number;
  nombre: string;
  activo: boolean;
}

export interface Product extends NamedRecord {
  sku: string;
}
export interface Movement {
  cantidad_anterior: number | null;
  cantidad_nueva: number | null;
  id: number;
  tipo: 'ENTRADA' | 'SALIDA' | 'VENTA' | 'AJUSTE' | 'TRASPASO';
  cantidad: number;
  motivo: string | null;
  referencia_tipo: string | null;
  referencia_id: number | null;
  usuario_id: number | null;
  created_at: string;
}

export type Operation = 'alta' | 'minimo' | 'entradas' | 'salidas' | 'ajustes' | 'traspasos';
export const actionLabels: Record<Operation, string> = {
  alta: 'Crear inventario',
  minimo: 'Modificar mínimo',
  entradas: 'Registrar entrada',
  salidas: 'Registrar salida',
  ajustes: 'Ajustar existencias',
  traspasos: 'Traspasar existencias',
};

export const mayOperate = (
  action: Operation,
  role: number,
  branch: number | null,
  item: Inventory | null,
) =>
  role === 1 ||
  (role === 2 &&
    branch !== null &&
    branch === item?.sucursal_id &&
    (action === 'entradas' || action === 'salidas'));

export const isLowStock = (item: Inventory) => item.cantidad <= item.stock_minimo;
export const stockLabel = (item: Inventory) =>
  item.cantidad === 0 ? 'Agotado' : isLowStock(item) ? 'Stock bajo' : 'Disponible';

export function validQuantity(action: Operation, value: number | null, available: number): boolean {
  if (value === null || !Number.isSafeInteger(value) || value < 0 || value > 2147483647)
    return false;
  switch (action) {
    case 'entradas':
      return value > 0 && value + available <= 2147483647;
    case 'salidas':
    case 'traspasos':
      return value > 0 && value <= available;
    case 'ajustes':
      return value !== available;
    default:
      return true;
  }
}

export function movementLabel(movement: Movement): string {
  if (movement.tipo === 'TRASPASO') {
    if (movement.referencia_tipo === 'INVENTARIO_ORIGEN') return 'Entrada por traspaso';
    if (movement.referencia_tipo === 'INVENTARIO_DESTINO') return 'Salida por traspaso';
  }
  const names: Record<Movement['tipo'], string> = {
    ENTRADA: 'Entrada',
    SALIDA: 'Salida',
    VENTA: 'Venta',
    AJUSTE: 'Ajuste',
    TRASPASO: 'Traspaso',
  };
  return names[movement.tipo];
}
