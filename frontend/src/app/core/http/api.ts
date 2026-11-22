import { inject, Injectable, signal } from '@angular/core';
import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { firstValueFrom, Observable } from 'rxjs';
import { API_BASE } from '../config/api-config';

export type Query = Record<string, string | number | boolean | null | undefined>;

@Injectable({ providedIn: 'root' })
export class Api {
  private readonly client = inject(HttpClient);
  private readonly base = inject(API_BASE);
  readonly changed = signal(0);

  private url(path: string) {
    if (!/^\/(?!\/)/.test(path)) throw new Error('Ruta de API inválida.');
    return this.base + path;
  }

  get<T>(path: string, query: Query = {}): Promise<T> {
    let params = new HttpParams();
    for (const [key, value] of Object.entries(query)) {
      if (value != null && value !== '') params = params.set(key, value);
    }
    return firstValueFrom(this.client.get<T>(this.url(path), { params }));
  }

  html(path: string): Promise<string> {
    return firstValueFrom(this.client.get(this.url(path), { responseType: 'text' }));
  }

  post<T>(path: string, body: unknown, key?: string): Promise<T> {
    const headers: Record<string, string> = key ? { 'Idempotency-Key': key } : {};
    return this.mutate(this.client.post<T>(this.url(path), body, { headers }));
  }

  patch<T>(path: string, body: unknown): Promise<T> {
    return this.mutate(this.client.patch<T>(this.url(path), body));
  }

  remove<T>(path: string): Promise<T> {
    return this.mutate(this.client.delete<T>(this.url(path)));
  }

  private async mutate<T>(request: Observable<T>) {
    const result = await firstValueFrom(request);
    this.changed.update((value) => value + 1);
    return result;
  }
}

const messages: Record<number, string> = {
  0: 'No se pudo conectar con el servidor. Comprueba tu conexión y vuelve a consultar la operación.',
  400: 'Comprueba los datos de la solicitud.',
  401: 'La sesión expiró o las credenciales son incorrectas.',
  403: 'Tu cuenta no tiene permiso para realizar esta acción.',
  404: 'El registro solicitado ya no está disponible.',
  409: 'El estado del registro cambió. Consulta el resultado antes de reintentar.',
  422: 'Revisa los campos del formulario.',
  429: 'Hay demasiadas solicitudes. Espera antes de reintentar.',
};

export function errorMessage(error: unknown): string {
  if (!(error instanceof HttpErrorResponse)) {
    return error instanceof Error ? error.message : 'No se pudo completar la operación.';
  }
  if (error.status >= 500)
    return 'El servidor no pudo completar la solicitud. Consulta el estado antes de reintentar.';
  const retry = error.status === 429 ? error.headers.get('Retry-After') : null;
  let body = error.error;
  if (typeof body === 'string') {
    try {
      body = JSON.parse(body);
    } catch {
      body = null;
    }
  }
  const detail: unknown = body?.detail;
  let message = messages[error.status] ?? 'No se pudo completar la solicitud.';
  if (typeof detail === 'string' && detail.length <= 600) message = detail;
  if (Array.isArray(detail)) {
    const issues = detail.slice(0, 8).filter((item) => typeof item?.msg === 'string');
    if (issues.length)
      message = issues
        .map((item) => {
          const field = Array.isArray(item.loc)
            ? item.loc.filter((key: unknown) => key !== 'body').join('.')
            : '';
          return [field, item.msg.slice(0, 240)].filter(Boolean).join(' · ');
        })
        .join('\n');
  }
  return retry && /^\d+$/.test(retry) ? message + ' Reintenta en ' + retry + ' segundos.' : message;
}
