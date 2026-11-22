import { Routes } from '@angular/router';
import { guestOnly, requireRole } from './core/auth/guards';

export const routes: Routes = [
  {
    path: 'incorporacion',
    title: 'Incorporación · DulceGestión',
    loadComponent: () =>
      import('./features/administration/invitation').then((m) => m.InvitationPage),
  },
  { path: '', pathMatch: 'full', redirectTo: 'login' },
  {
    path: 'login',
    canMatch: [guestOnly],
    loadComponent: () => import('./features/auth/login/login').then((m) => m.LoginPage),
  },
  {
    path: 'admin',
    canMatch: [requireRole(1)],
    loadChildren: () => import('./features/admin/admin.routes').then((m) => m.ADMIN_ROUTES),
  },
  {
    path: 'employee',
    canMatch: [requireRole(2)],
    loadChildren: () =>
      import('./features/employee/employee.routes').then((m) => m.EMPLOYEE_ROUTES),
  },
  { path: '**', redirectTo: 'login' },
];
