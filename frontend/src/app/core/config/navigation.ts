export interface NavItem {
  path: string;
  label: string;
  icon: string;
}

export const ADMIN_GROUPS: { label: string; items: NavItem[] }[] = [
  {
    label: 'Supervisión',
    items: [
      { path: 'dashboard', label: 'Resumen', icon: 'dashboard' },
      { path: 'reports', label: 'Reportes', icon: 'chart' },
    ],
  },
  {
    label: 'Operación',
    items: [
      { path: 'orders', label: 'Pedidos', icon: 'orders' },
      { path: 'sales', label: 'Ventas', icon: 'sales' },
      { path: 'payments', label: 'Pagos', icon: 'payment' },
      { path: 'tickets', label: 'Tickets', icon: 'ticket' },
      { path: 'invoices', label: 'Facturas', icon: 'invoice' },
    ],
  },
  {
    label: 'Catálogo y existencias',
    items: [
      { path: 'products', label: 'Productos', icon: 'cake' },
      { path: 'categories', label: 'Categorías', icon: 'tags' },
      { path: 'inventory', label: 'Inventario', icon: 'stock' },
    ],
  },
  {
    label: 'Organización',
    items: [
      { path: 'branches', label: 'Sucursales', icon: 'store' },
      { path: 'requests', label: 'Expedientes', icon: 'shield' },
      { path: 'imports', label: 'Importar empleados', icon: 'orders' },
      { path: 'employees', label: 'Empleados', icon: 'staff' },
      { path: 'users', label: 'Usuarios', icon: 'user' },
      { path: 'customers', label: 'Clientes', icon: 'contacts' },
    ],
  },
  {
    label: 'Configuración',
    items: [
      { path: 'identity', label: 'Identidad empresarial', icon: 'store' },
      { path: 'benefits', label: 'Beneficios', icon: 'staff' },
    ],
  },
];

export const ADMIN_NAV = ADMIN_GROUPS.flatMap((group) => group.items);
export const EMPLOYEE_NAV: NavItem[] = [
  { path: 'pos', label: 'Punto de venta', icon: 'pos' },
  { path: 'orders', label: 'Pedidos', icon: 'orders' },
  { path: 'sales', label: 'Ventas', icon: 'sales' },
  { path: 'payments', label: 'Pagos', icon: 'payment' },
  { path: 'tickets', label: 'Tickets', icon: 'ticket' },
  { path: 'invoices', label: 'Facturas', icon: 'invoice' },
  { path: 'inventory', label: 'Inventario', icon: 'stock' },
  { path: 'profile', label: 'Mi perfil', icon: 'user' },
];
