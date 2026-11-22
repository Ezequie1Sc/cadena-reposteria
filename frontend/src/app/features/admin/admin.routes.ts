import { Routes } from '@angular/router';
import { AdminLayout } from '../../layouts/admin-layout/admin-layout';
import { operationalRoutes } from '../../core/config/operational-routes';

const catalog = () => import('./catalog/catalog').then((module) => module.CatalogPage);
export const ADMIN_ROUTES: Routes = [
  {
    path: '',
    component: AdminLayout,
    children: [
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
      {
        path: 'dashboard',
        title: 'Resumen · DulceGestión',
        loadComponent: () => import('./dashboard/pages/dashboard').then((m) => m.DashboardPage),
      },
      {
        path: 'products',
        title: 'Productos · DulceGestión',
        data: { resource: 'productos' },
        loadComponent: catalog,
      },
      {
        path: 'categories',
        title: 'Categorías · DulceGestión',
        data: { resource: 'categorias' },
        loadComponent: catalog,
      },
      {
        path: 'branches',
        title: 'Sucursales · DulceGestión',
        data: { resource: 'sucursales' },
        loadComponent: catalog,
      },
      {
        path: 'employees',
        title: 'Empleados · DulceGestión',
        data: { resource: 'empleados' },
        loadComponent: catalog,
      },
      {
        path: 'users',
        title: 'Usuarios · DulceGestión',
        data: { resource: 'usuarios' },
        loadComponent: catalog,
      },
      {
        path: 'customers',
        title: 'Clientes · DulceGestión',
        data: { resource: 'clientes' },
        loadComponent: catalog,
      },
      {
        path: 'products/new',
        title: 'Nuevo producto · DulceGestión',
        loadComponent: () => import('../administration/product-entry').then((m) => m.ProductEntry),
      },
      {
        path: 'employees/new',
        title: 'Registrar empleado · DulceGestión',
        loadComponent: () => import('../administration/team').then((m) => m.HirePage),
      },
      {
        path: 'requests',
        title: 'Expedientes · DulceGestión',
        loadComponent: () => import('../administration/team').then((m) => m.RequestsPage),
      },
      {
        path: 'imports',
        title: 'Importación · DulceGestión',
        loadComponent: () => import('../administration/imports-page').then((m) => m.ImportsPage),
      },
      {
        path: 'identity',
        title: 'Identidad empresarial · DulceGestión',
        loadComponent: () => import('../administration/company').then((m) => m.IdentityPage),
      },
      {
        path: 'benefits',
        title: 'Beneficios · DulceGestión',
        loadComponent: () => import('../administration/company').then((m) => m.BenefitsPage),
      },
      ...operationalRoutes(),
      {
        path: 'reports',
        title: 'Reportes · DulceGestión',
        loadComponent: () => import('./reports/pages/reports').then((m) => m.ReportsPage),
      },
      { path: '**', redirectTo: 'dashboard' },
    ],
  },
];
