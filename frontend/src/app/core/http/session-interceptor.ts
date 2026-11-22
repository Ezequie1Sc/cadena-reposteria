import { inject } from '@angular/core';
import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { catchError, throwError } from 'rxjs';
import { ToastService } from '../../shared/services/toast.service';
import { errorMessage } from './api';
import { API_BASE } from '../config/api-config';
import { AuthService } from '../auth/auth';

export const sessionInterceptor: HttpInterceptorFn = (request, next) => {
  const base = inject(API_BASE);
  if (!request.url.startsWith(base + '/')) return next(request);
  const toast = inject(ToastService);
  const publicRoute = [
    '/auth/login',
    '/incorporacion/codigo',
    '/incorporacion/verificar',
    '/incorporacion/solicitud',
  ].includes(request.url.slice(base.length));
  if (publicRoute)
    return next(request).pipe(
      catchError((error) => {
        toast.show('error', 'Solicitud no completada', errorMessage(error));
        return throwError(() => error);
      }),
    );
  const session = inject(AuthService);
  const token = session.token();
  if (!token) return throwError(() => new HttpErrorResponse({ status: 401 }));
  return next(request.clone({ setHeaders: { Authorization: 'Bearer ' + token } })).pipe(
    catchError((error) => {
      if (error instanceof HttpErrorResponse && error.status === 401 && session.token() === token)
        session.expire();
      if (error.status !== 401)
        toast.show(
          error.status === 403 || error.status === 409 ? 'warning' : 'error',
          'Solicitud no completada',
          errorMessage(error),
        );
      return throwError(() => error);
    }),
  );
};
