import { inject } from '@angular/core';
import { CanMatchFn, Router } from '@angular/router';
import { AuthService } from './auth';

export function requireRole(role: number): CanMatchFn {
  return () => {
    const auth = inject(AuthService);
    const router = inject(Router);
    if (!auth.token() || !auth.user()) return router.parseUrl('/login');
    return auth.user()?.rol_id === role || router.parseUrl(auth.home);
  };
}

export const guestOnly: CanMatchFn = () => {
  const auth = inject(AuthService);
  return !auth.token() || !auth.user() || inject(Router).parseUrl(auth.home);
};
