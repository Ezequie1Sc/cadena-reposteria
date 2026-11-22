import { Action, Entry, Method } from './models';
export interface Field {
  name: string;
  label: string;
  type?: 'text' | 'email' | 'number' | 'select' | 'textarea' | 'datetime-local' | 'checkbox';
  min?: number;
  max?: number;
  pattern?: string;
  choices?: { value: string; label: string }[];
  optional?: boolean;
}
export interface Task {
  action: Action;
  title: string;
  consequence: string;
  target?: string;
  danger?: boolean;
}
export const tasks = {
  order: {
    action: 'crear-pedido',
    title: 'Registrar pedido',
    consequence: 'Se reservarán las unidades solicitadas en la sucursal seleccionada.',
  },
  payment: {
    action: 'pagar',
    title: 'Registrar pago',
    consequence: 'El pago quedará pendiente hasta que el personal verifique el cobro.',
  },
  invoice: {
    action: 'facturar',
    title: 'Solicitar factura',
    consequence: 'Se registrarán los datos del receptor para su revisión fiscal.',
  },
  cancel: {
    action: 'cancelar-venta',
    title: 'Cancelar venta',
    consequence: 'Se cancelará la operación y se devolverán las existencias de la reserva.',
    danger: true,
  },
} satisfies Record<string, Task>;
export function transition(
  action: Action,
  target: string,
  title: string,
  consequence: string,
  danger = false,
): Task {
  return { action, target, title, consequence, danger };
}
export function actionFields(
  task: Task,
  row: Entry | null,
  admin: boolean,
  methods: Method[],
  values: Record<string, string>,
): Field[] {
  const reason: Field = { name: 'motivo', label: 'Motivo', type: 'textarea', min: 3, max: 500 };
  const field = (name: string, label: string, options: Partial<Field> = {}): Field => ({
    name,
    label,
    ...options,
  });
  const ref = field('referencia_proveedor', 'Referencia del proveedor', { min: 3, max: 255 });
  const choices = (values: string[]) => values.map((value) => ({ value, label: value }));
  switch (task.action) {
    case 'crear-pedido':
      return [
        ...(admin ? [field('sucursal_id', 'Sucursal', { type: 'number', min: 1 })] : []),
        field('cliente_id', 'ID del cliente', { type: 'number', min: 1 }),
        field('notas', 'Notas del pedido', { type: 'textarea', optional: true, max: 2000 }),
      ];
    case 'pagar':
      return [
        field('metodo', 'Método de pago', {
          type: 'select',
          choices: methods.map((m) => ({ value: m.codigo, label: m.nombre })),
        }),
        ...(values['metodo'] && values['metodo'] !== 'EFECTIVO'
          ? [field('referencia', 'Referencia de la operación', { min: 3, max: 255 })]
          : []),
      ];
    case 'cancelar-venta':
      return [
        reason,
        ...(row?.estado === 'CONFIRMADA'
          ? [
              field('reembolso_referencia', 'Referencia de la devolución total realizada', {
                min: 3,
                max: 255,
              }),
              field('verificado', 'Verifiqué la devolución total fuera del sistema.', {
                type: 'checkbox',
              }),
            ]
          : []),
      ];
    case 'pedido-estado':
      return [];
    case 'pago-estado':
      return [
        reason,
        ...(task.target === 'APROBADO'
          ? [
              field(
                'verificado',
                'Verifiqué la recepción del importe completo en efectivo, terminal o cuenta bancaria.',
                { type: 'checkbox' },
              ),
            ]
          : []),
      ];
    case 'facturar':
      return [
        ...(row?.cliente_id == null
          ? [
              field('cliente_id', 'ID del cliente que se vinculará a la venta', {
                type: 'number',
                min: 1,
              }),
            ]
          : []),
        field('tipo_persona', 'Tipo de persona', {
          type: 'select',
          choices: choices(['FISICA', 'MORAL']),
        }),
        field('rfc', 'RFC', {
          pattern:
            values['tipo_persona'] === 'MORAL'
              ? '[A-ZÑ&]{3}[0-9]{6}[A-Z0-9]{3}'
              : '[A-ZÑ&]{4}[0-9]{6}[A-Z0-9]{3}',
        }),
        field('razon_social', 'Razón social', { min: 3, max: 255 }),
        field('uso_cfdi', 'Uso de CFDI', { pattern: '[A-Z][0-9]{2}' }),
        field('codigo_postal_fiscal', 'Código postal fiscal', { pattern: '[0-9]{5}' }),
        field('regimen_fiscal', 'Régimen fiscal', { pattern: '[0-9]{3}' }),
        field('direccion_fiscal', 'Domicilio fiscal', { min: 5, max: 500 }),
        field('email_fiscal', 'Correo fiscal', { type: 'email' }),
      ];
    case 'factura-estado':
      if (task.target === 'EMITIDA')
        return [
          reason,
          field('uuid', 'UUID del documento externo', {
            pattern: '[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}',
          }),
          field('proveedor', 'Proveedor emisor', { min: 3, max: 100 }),
          ref,
          field('fecha_emision', 'Fecha y hora de emisión local', { type: 'datetime-local' }),
        ];
      return [reason, ...(row?.estado === 'EMITIDA' ? [ref] : [])];
  }
}
