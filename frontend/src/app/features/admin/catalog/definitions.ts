export type CatalogName =
  'productos' | 'categorias' | 'sucursales' | 'empleados' | 'usuarios' | 'clientes';
export type Scalar = string | number | boolean | null;
export interface CatalogRecord {
  id: number;
  activo: boolean;
  [field: string]: Scalar;
}
export interface Field {
  key: string;
  label: string;
  kind?:
    'text' | 'email' | 'password' | 'date' | 'integer' | 'decimal' | 'textarea' | 'select' | 'tel';
  required?: boolean;
  min?: number;
  max?: number;
  minLength?: number;
  maxLength?: number;
  source?: 'categorias' | 'sucursales' | 'roles';
  pattern?: RegExp;
}
export interface Definition {
  title: string;
  singular: string;
  create: string;
  description: string;
  disabledEffect: string;
  columns: string[];
  fields: Field[];
}
const name = (minLength = 1, maxLength = 100): Field => ({
  key: 'nombre',
  label: 'Nombre',
  required: true,
  minLength,
  maxLength,
});
const lastname: Field = { key: 'apellido', label: 'Apellido', maxLength: 100 };
const phone: Field = { key: 'telefono', label: 'Teléfono', kind: 'tel', maxLength: 20 };
const email: Field = { key: 'email', label: 'Correo electrónico', kind: 'email', maxLength: 254 };
const user: Field = {
  key: 'usuario_id',
  label: 'ID de cuenta de usuario',
  kind: 'integer',
  min: 1,
};
const description: Field = { key: 'descripcion', label: 'Descripción', kind: 'textarea' };
export const catalogDefinitions: Record<CatalogName, Definition> = {
  productos: {
    title: 'Productos',
    singular: 'producto',
    create: 'Nuevo producto',
    description: 'Precios, categorías y disponibilidad en el catálogo.',
    disabledEffect: 'El producto dejará de aparecer en el catálogo activo para nuevas ventas.',
    columns: ['nombre', 'sku', 'categoria_id', 'precio'],
    fields: [
      name(2, 150),
      { key: 'sku', label: 'SKU', required: true, maxLength: 50 },
      {
        key: 'categoria_id',
        label: 'Categoría',
        kind: 'select',
        source: 'categorias',
        required: true,
      },
      {
        key: 'precio',
        label: 'Precio (MXN)',
        kind: 'decimal',
        required: true,
        pattern: /^\d{1,10}(\.\d{1,2})?$/,
      },
      description,
      { key: 'imagen_url', label: 'Dirección de imagen', maxLength: undefined },
    ],
  },
  categorias: {
    title: 'Categorías',
    singular: 'categoría',
    create: 'Nueva categoría',
    description: 'Organiza los productos para su consulta en tienda.',
    disabledEffect: 'La categoría dejará de aparecer entre las categorías activas.',
    columns: ['nombre', 'descripcion'],
    fields: [name(2), description],
  },
  sucursales: {
    title: 'Sucursales',
    singular: 'sucursal',
    create: 'Nueva sucursal',
    description: 'Ubicación y datos de contacto de cada punto de venta.',
    disabledEffect: 'La sucursal dejará de estar disponible para nuevas operaciones.',
    columns: ['nombre', 'codigo', 'ciudad', 'estado'],
    fields: [
      name(),
      { key: 'codigo', label: 'Código', required: true, maxLength: 30 },
      { key: 'direccion', label: 'Dirección', required: true, maxLength: 255 },
      { key: 'ciudad', label: 'Ciudad', required: true, maxLength: 100 },
      { key: 'estado', label: 'Estado o entidad', required: true, maxLength: 100 },
      { key: 'codigo_postal', label: 'Código postal', maxLength: 10 },
      phone,
      { key: 'latitud', label: 'Latitud', kind: 'decimal', min: -90, max: 90 },
      { key: 'longitud', label: 'Longitud', kind: 'decimal', min: -180, max: 180 },
    ],
  },
  empleados: {
    title: 'Empleados',
    singular: 'empleado',
    create: 'Nuevo empleado',
    description: 'Personal operativo, puestos y sucursales asignadas.',
    disabledEffect: 'El empleado dejará de estar activo para operar en su sucursal.',
    columns: ['numero_empleado', 'puesto', 'sucursal_id', 'usuario_id'],
    fields: [
      { key: 'numero_empleado', label: 'Número de empleado', required: true, maxLength: 30 },
      { key: 'puesto', label: 'Puesto', required: true, maxLength: 100 },
      { ...user, required: true },
      {
        key: 'sucursal_id',
        label: 'Sucursal',
        kind: 'select',
        source: 'sucursales',
        required: true,
      },
    ],
  },
  usuarios: {
    title: 'Usuarios',
    singular: 'usuario',
    create: 'Nueva cuenta',
    description: 'Cuentas de acceso, datos personales y roles asignados.',
    disabledEffect: 'La cuenta perderá acceso al sistema.',
    columns: ['nombre', 'apellido', 'email', 'rol_id'],
    fields: [
      name(),
      { ...lastname, required: true },
      { ...email, required: true },
      phone,
      { key: 'rol_id', label: 'Rol', kind: 'select', source: 'roles', required: true },
      {
        key: 'password',
        label: 'Contraseña',
        kind: 'password',
        required: true,
        minLength: 12,
        maxLength: 128,
      },
    ],
  },
  clientes: {
    title: 'Clientes',
    singular: 'cliente',
    create: 'Nuevo cliente',
    description: 'Datos de contacto y vínculo con la cuenta del cliente.',
    disabledEffect: 'El cliente se retirará de los listados de clientes activos.',
    columns: ['nombre', 'apellido', 'email', 'telefono'],
    fields: [
      name(2),
      lastname,
      email,
      { ...phone, minLength: 7, pattern: /^\+?[0-9\s()-]+$/ },
      { key: 'fecha_nacimiento', label: 'Fecha de nacimiento', kind: 'date' },
      user,
    ],
  },
};
export function labelFor(def: Definition, key: string): string {
  return (
    def.fields.find((f) => f.key === key)?.label ??
    (
      {
        id: 'Identificador',
        activo: 'Estado del registro',
        created_at: 'Fecha de registro',
        updated_at: 'Última actualización',
      } as Record<string, string>
    )[key] ??
    key
  );
}
