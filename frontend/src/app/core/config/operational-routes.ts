import { Routes } from '@angular/router';

const commerce = () =>
  import('../../features/commerce/commerce').then((module) => module.CommercePage);

export function operationalRoutes(): Routes {
  return [
    {
      path: 'inventory',
      title: 'Inventario · DulceGestión',
      loadComponent: () =>
        import('../../features/inventory/inventory').then((module) => module.InventoryPage),
    },
    {
      path: 'orders',
      title: 'Pedidos · DulceGestión',
      data: { resource: 'pedidos' },
      loadComponent: commerce,
    },
    {
      path: 'sales',
      title: 'Ventas · DulceGestión',
      data: { resource: 'ventas' },
      loadComponent: commerce,
    },
    {
      path: 'payments',
      title: 'Pagos · DulceGestión',
      data: { resource: 'pagos' },
      loadComponent: commerce,
    },
    {
      path: 'tickets',
      title: 'Tickets · DulceGestión',
      data: { resource: 'tickets' },
      loadComponent: commerce,
    },
    {
      path: 'invoices',
      title: 'Facturas · DulceGestión',
      data: { resource: 'facturas' },
      loadComponent: commerce,
    },
  ];
}
