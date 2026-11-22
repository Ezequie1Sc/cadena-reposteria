import { computed, inject, Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ToastService } from '../../shared/services/toast.service';
import { API_BASE } from '../config/api-config';

export interface SessionProfile {
  id: number;
  rol_id: number;
  nombre: string;
  apellido: string;
  email: string;
  activo: boolean;
  cliente_id: number | null;
  sucursal_id: number | null;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly toast = inject(ToastService);
  private readonly http = inject(HttpClient);
  private readonly base = inject(API_BASE);
  private readonly router = inject(Router);
  private readonly current = signal<SessionProfile | null>(null);
  readonly user = this.current.asReadonly();
  readonly isAdmin = computed(() => this.user()?.rol_id === 1);
  readonly notice = signal('');
  private accessToken: string | null = null;
  private expiryTimer?: ReturnType<typeof setTimeout>;
  private deadline = 0;

  get home() {
    return this.isAdmin() ? '/admin/dashboard' : '/employee/pos';
  }

  token(): string | null {
    if (this.accessToken && this.deadline <= Date.now()) this.expire();
    return this.accessToken;
  }

  async login(email: string, password: string) {
    this.clear();
    this.notice.set('');
    const result = await firstValueFrom(
      this.http.post<{ access_token: string; token_type: string }>(this.base + '/auth/login', {
        email: email.trim(),
        password,
      }),
    );
    try {
      const encoded = result.access_token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
      const exp: unknown = JSON.parse(atob(encoded)).exp;
      if (
        result.token_type !== 'bearer' ||
        typeof exp !== 'number' ||
        !Number.isFinite(exp) ||
        exp * 1000 <= Date.now()
      )
        throw new Error();
      this.accessToken = result.access_token;
      this.deadline = exp * 1000;
      this.scheduleExpiration();
    } catch {
      this.clear();
      throw new Error('El servidor devolvió una sesión inválida o vencida.');
    }
    try {
      const user = await firstValueFrom(this.http.get<SessionProfile>(this.base + '/auth/me'));
      if (!user.activo || ![1, 2].includes(user.rol_id))
        throw new Error(
          'El acceso a este portal está reservado a empleados y administradores activos.',
        );
      if (this.token() !== result.access_token)
        throw new Error('La sesión venció. Vuelve a ingresar.');
      this.current.set(user);
    } catch (error) {
      this.clear();
      throw error;
    }
  }

  private scheduleExpiration() {
    const remaining = this.deadline - Date.now();
    if (remaining <= 0) return this.expire();
    this.expiryTimer = setTimeout(() => this.scheduleExpiration(), Math.min(remaining, 2147483647));
  }

  expire() {
    this.clear();
    this.toast.show('info', 'Sesión finalizada', 'Ingresa de nuevo para continuar.');
    this.notice.set('Tu sesión venció. Ingresa de nuevo para continuar.');
    void this.router.navigateByUrl('/login', { replaceUrl: true });
  }

  logout() {
    this.clear();
    this.notice.set('');
    void this.router.navigateByUrl('/login', { replaceUrl: true });
  }

  private clear() {
    this.toast.clear();
    clearTimeout(this.expiryTimer);
    this.accessToken = null;
    this.deadline = 0;
    this.current.set(null);
  }
}
