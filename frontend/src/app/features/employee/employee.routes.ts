import { Routes } from '@angular/router';
import { EmployeeLayout } from '../../layouts/employee-layout/employee-layout';
import { operationalRoutes } from '../../core/config/operational-routes';

export const EMPLOYEE_ROUTES: Routes = [
  {
    path: '',
    component: EmployeeLayout,
    children: [
      { path: '', redirectTo: 'pos', pathMatch: 'full' },
      {
        path: 'pos',
        title: 'Punto de venta · DulceGestión',
        loadComponent: () =>
          import('./point-of-sale/pages/point-of-sale').then((m) => m.PointOfSalePage),
      },
      { path: 'point-of-sale', redirectTo: 'pos' },
      { path: 'dashboard', redirectTo: 'pos' },
      ...operationalRoutes(),
      {
        path: 'profile',
        title: 'Mi perfil · DulceGestión',
        loadComponent: () => import('./profile/pages/profile').then((m) => m.ProfilePage),
      },
      { path: '**', redirectTo: 'pos' },
    ],
  },
];
