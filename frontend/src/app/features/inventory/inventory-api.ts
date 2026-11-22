import { Injectable, inject } from '@angular/core';
import { Api } from '../../core/http/api';
import type { Inventory, Movement, NamedRecord, Operation, Product } from './inventory.models';

@Injectable({ providedIn: 'root' })
export class InventoryApi {
  private readonly api = inject(Api);

  async catalog(admin: boolean) {
    const params = { solo_activos: !admin };
    const [products, branches, entries] = await Promise.all([
      this.api.get<{ productos: Product[] }>('/productos', params),
      this.api.get<{ sucursales: NamedRecord[] }>('/sucursales', params),
      this.api.get<{ inventarios: Inventory[] }>('/inventarios'),
    ]);
    return {
      products: products.productos,
      branches: branches.sucursales,
      entries: entries.inventarios,
    };
  }

  get(id: number) {
    return this.api.get<Inventory>(`/inventarios/${id}`);
  }

  history(id: number, limit: number, offset: number) {
    return this.api.get<{ movimientos: Movement[] }>(`/inventarios/${id}/movimientos`, {
      limit,
      offset,
    });
  }

  apply(
    action: Operation,
    id: number | undefined,
    body: Record<string, number | string>,
    key: string,
  ) {
    if (action === 'alta') return this.api.post<Inventory>('/inventarios', body);
    if (!id) throw new Error('Selecciona un registro de inventario.');
    const path = `/inventarios/${id}`;
    if (action === 'minimo') return this.api.patch<Inventory>(path, body);
    const tipos = {
      entradas: 'entrada',
      salidas: 'salida',
      ajustes: 'ajuste',
      traspasos: 'traspaso',
    };
    return this.api
      .post('/inventario-operativo/' + id + '/movimiento', { ...body, tipo: tipos[action] }, key)
      .then(() => this.get(id));
  }
}
