import { Injectable, inject } from '@angular/core';
import { Api } from '../../core/http/api';
import { AuthService } from '../../core/auth/auth';
import { Entry, EventEntry, Resource } from './models';

export interface Filters {
  estado: string;
  sucursal: string;
  desde: string;
  hasta: string;
  metodo: string;
  cliente: string;
  empleado: string;
}
export const initialFilters = (): Filters => ({
  estado: '',
  sucursal: '',
  desde: '',
  hasta: '',
  metodo: '',
  cliente: '',
  empleado: '',
});
type ListEnvelope = { total: number } & Partial<Record<Resource, Entry[]>>;
export const pageSize = 20;

@Injectable({ providedIn: 'root' })
export class CommercialApi {
  readonly api = inject(Api);
  private readonly auth = inject(AuthService);
  private readonly pending = new Map<string, string>();

  async list(resource: Resource, filters: Filters, offset: number) {
    const end = filters.hasta ? new Date(filters.hasta + 'T00:00:00') : null;
    if (end) end.setDate(end.getDate() + 1);
    const params = {
      limit: pageSize,
      offset,
      estado: filters.estado || undefined,
      metodo: filters.metodo || undefined,
      sucursal_id: filters.sucursal || undefined,
      cliente_id: filters.cliente || undefined,
      empleado_id: filters.empleado || undefined,
      desde: filters.desde ? new Date(filters.desde + 'T00:00:00').toISOString() : undefined,
      hasta: end?.toISOString(),
    };
    const data = await this.api.get<Entry[] | ListEnvelope>('/' + resource, params);
    if (Array.isArray(data)) return { rows: data, total: null, more: data.length === pageSize };
    return { rows: data[resource] ?? [], total: data.total, more: offset + pageSize < data.total };
  }
  detail(resource: Resource, id: number) {
    return this.api.get<Entry>('/' + resource + '/' + id);
  }
  history(resource: Resource, id: number, offset: number) {
    return this.api.get<EventEntry[]>('/' + resource + '/' + id + '/historial', {
      limit: pageSize,
      offset,
    });
  }

  // Only the digest and UUID are stored, never fiscal data, payment references or the JWT.
  async create(resource: 'pagos' | 'pedidos' | 'facturas', body: unknown): Promise<Entry> {
    const actor = this.auth.user();
    if (!actor) throw new Error('La sesión terminó.');
    const bytes = await crypto.subtle.digest(
      'SHA-256',
      new TextEncoder().encode(JSON.stringify(body)),
    );
    const fingerprint = Array.from(new Uint8Array(bytes), (byte) =>
      byte.toString(16).padStart(2, '0'),
    ).join('');
    const storageKey = 'dulce.intent.' + actor.id + '.' + resource + '.' + fingerprint;
    const key =
      sessionStorage.getItem(storageKey) || this.pending.get(storageKey) || crypto.randomUUID();
    this.pending.set(storageKey, key);
    sessionStorage.setItem(storageKey, key);
    const result = await this.api.post<Entry>('/' + resource, body, key);
    this.pending.delete(storageKey);
    sessionStorage.removeItem(storageKey);
    return result;
  }
}
