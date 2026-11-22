import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpEventType, HttpResponse } from '@angular/common/http';
import { firstValueFrom, filter, tap } from 'rxjs';
import { Api } from '../../core/http/api';
import { API_BASE } from '../../core/config/api-config';

export interface Choice {
  id: number;
  nombre: string;
  activo: boolean;
}
export interface Hire {
  nombre: string;
  apellido: string;
  puesto: string;
  email: string;
  sucursal_id: number;
}
export interface Profile extends Hire {
  empleado_id: number;
  usuario_id: number;
  numero_empleado: string;
  sucursal: string;
  creado: string;
  estado: string;
}
export interface Identity {
  nombre: string;
  logotipo: string | null;
  color: string;
  mensaje: string;
  firma: string;
  contacto: string;
}
export interface Benefit {
  nombre: string;
  condiciones: string;
  activo: boolean;
  inicio: string | null;
  fin: string | null;
  puesto: string | null;
  sucursal_id: number | null;
  empleado_id: number | null;
}
export interface Batch {
  id: number;
  estado: string;
  filas: {
    fila: number;
    estado: string;
    datos: Record<string, string>;
    error?: string;
    empleado_id?: number;
  }[];
}
export interface ProductInput {
  nombre: string;
  categoria_id: number;
  precio: string;
  descripcion: string | null;
  inventarios: { sucursal_id: number; existencias_iniciales: number; stock_minimo: number }[];
}
export interface Photo {
  imagen_id: number;
  producto_id: number;
  url: string;
}
export interface Created {
  producto: { id: number; sku: string; nombre: string };
  inventarios: { id: number; sucursal_id: number; cantidad: number; stock_minimo: number }[];
}
export type Decision = 'aprobar' | 'rechazar' | 'correccion' | 'revocar' | 'reinvitar';
export interface Welcome {
  pendiente: boolean;
  empleado?: Profile;
  identidad?: Identity;
  beneficios?: Pick<Benefit, 'nombre' | 'condiciones'>[];
}
@Injectable({ providedIn: 'root' })
export class AdministrationApi {
  private api = inject(Api);
  private http = inject(HttpClient);
  private base = inject(API_BASE);
  branches() {
    return this.api
      .get<{ sucursales: Choice[] }>('/sucursales', { solo_activos: true })
      .then((v) => v.sucursales);
  }
  categories() {
    return this.api
      .get<{ categorias: Choice[] }>('/categorias', { solo_activos: true })
      .then((v) => v.categorias);
  }
  createProduct(body: ProductInput, key: string) {
    return this.api.post<Created>('/administracion/productos', body, key);
  }
  async upload<T extends Photo>(
    path: string,
    file: File,
    key: string,
    progress: (n: number | null) => void,
    data?: ProductInput,
  ) {
    const body = new FormData();
    body.set('archivo', file);
    if (data) body.set('datos', JSON.stringify(data));
    const result = await firstValueFrom(
      this.http
        .request<T>(data ? 'POST' : 'PUT', this.base + path, {
          body,
          headers: { 'Idempotency-Key': key },
          observe: 'events',
          reportProgress: true,
        })
        .pipe(
          tap((e) => {
            if (e.type === HttpEventType.UploadProgress)
              progress(e.total ? Math.round((100 * e.loaded) / e.total) : null);
          }),
          filter((e): e is HttpResponse<T> => e.type === HttpEventType.Response),
        ),
    );
    if (!result.body) throw new Error('La API no devolvió el recibo de la fotografía.');
    this.api.changed.update((n) => n + 1);
    return result.body;
  }
  removePhoto(id: number, image: number) {
    return this.api.remove('/administracion/productos/' + id + '/imagenes/' + image);
  }
  hire(body: Hire, key: string) {
    return this.api.post<Profile>('/administracion/empleados', body, key);
  }
  requests(estado: string, offset: number) {
    return this.api.get<Profile[]>('/administracion/solicitudes', { estado, offset });
  }
  history(id: number) {
    return this.api.get<
      { accion: string; fecha: string; motivo: string | null; actor_id: number | null }[]
    >('/administracion/solicitudes/' + id + '/historial');
  }
  decide(id: number, accion: Decision, motivo: string | null, key: string) {
    return this.api.post<{ estado: string }>(
      '/administracion/solicitudes/' + id + '/decision',
      { accion, motivo },
      key,
    );
  }
  preview(file: File) {
    const body = new FormData();
    body.set('archivo', file);
    return this.api.post<Batch>('/administracion/importaciones/vista-previa', body);
  }
  batch(id: number) {
    return this.api.get<Batch>('/administracion/importaciones/' + id);
  }
  confirm(id: number) {
    return this.api.post<{ estado: string }>(
      '/administracion/importaciones/' + id + '/confirmar',
      {},
    );
  }
  csv(id?: number) {
    return firstValueFrom(
      this.http.get(
        this.base + '/administracion/importaciones/' + (id ? id + '/errores.csv' : 'plantilla'),
        { responseType: 'blob' },
      ),
    );
  }
  identity() {
    return this.api.get<Identity | null>('/administracion/identidad');
  }
  saveIdentity(body: Identity) {
    return firstValueFrom(this.http.put<Identity>(this.base + '/administracion/identidad', body));
  }
  benefits() {
    return this.api.get<(Benefit & { id: number })[]>('/administracion/beneficios');
  }
  saveBenefit(body: Benefit, id?: number) {
    return id
      ? firstValueFrom(this.http.put<Benefit>(this.base + '/administracion/beneficios/' + id, body))
      : this.api.post<Benefit>('/administracion/beneficios', body);
  }
  code(token: string) {
    return this.api.post('/incorporacion/codigo', { token });
  }
  verify(token: string, codigo: string) {
    return this.api.post<{ comprobante: string }>('/incorporacion/verificar', { token, codigo });
  }
  submit(
    token: string,
    codigo: string,
    body: { nombre: string; apellido: string; password: string },
  ) {
    return this.api.post('/incorporacion/solicitud', { token, codigo, ...body });
  }
  welcome() {
    return this.api.get<Welcome>('/empleado/bienvenida');
  }
  acknowledge() {
    return this.api.post('/empleado/bienvenida/vista', {});
  }
}
