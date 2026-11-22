import { EmptyState, Skeleton } from '../../shared/components/feedback/feedback';
import { DatePipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../core/auth/auth';
import { errorMessage } from '../../core/http/api';
import { InventoryApi } from './inventory-api';
import { InventoryEditor } from './inventory-editor';
import { MovementHistory } from './movement-history';
import {
  Inventory,
  NamedRecord,
  Operation,
  Product,
  actionLabels,
  isLowStock,
  mayOperate,
  stockLabel,
} from './inventory.models';

@Component({
  standalone: true,
  selector: 'app-inventory',
  imports: [EmptyState, Skeleton, DatePipe, FormsModule, InventoryEditor, MovementHistory],
  templateUrl: './inventory.html',
  styleUrl: './inventory.css',
})
export class InventoryPage {
  readonly auth = inject(AuthService);
  private readonly api = inject(InventoryApi);
  readonly inventories = signal<Inventory[]>([]);
  readonly productList = signal<Product[]>([]);
  readonly branchList = signal<NamedRecord[]>([]);
  readonly products = computed(() => new Map(this.productList().map((p) => [p.id, p])));
  readonly branches = computed(() => new Map(this.branchList().map((b) => [b.id, b])));
  readonly search = signal('');
  readonly branch = signal<number | null>(null);
  readonly low = signal(false);
  readonly page = signal(0);
  readonly pageSize = 15;
  readonly loading = signal(true);
  readonly error = signal('');
  readonly selected = signal<Inventory | null>(null);
  readonly detailId = signal<number | null>(null);
  readonly detailLoading = signal(false);
  readonly detailError = signal('');
  readonly revision = signal(0);
  readonly action = signal<Operation | null>(null);
  readonly label = stockLabel;
  readonly labels = actionLabels;
  private listRequest = 0;
  private detailRequest = 0;

  readonly filtered = computed(() => {
    const query = this.search().trim().toLocaleLowerCase('es');
    const branch = this.branch();
    const items = this.inventories();
    return items.filter((item) => {
      const p = this.products().get(item.producto_id);
      const title = `${p?.nombre ?? ''} ${p?.sku ?? ''} ${item.producto_id}`.toLocaleLowerCase(
        'es',
      );
      return (
        (!branch || item.sucursal_id === branch) &&
        (!this.low() || isLowStock(item)) &&
        title.includes(query)
      );
    });
  });
  readonly visible = computed(() =>
    this.filtered().slice(this.page() * this.pageSize, (this.page() + 1) * this.pageSize),
  );
  readonly pageCount = computed(() => Math.ceil(this.filtered().length / this.pageSize));
  readonly actions = computed(() => {
    const actor = this.auth.user();
    const item = this.selected();
    if (!actor || !item) return [];
    const active =
      this.products().get(item.producto_id)?.activo &&
      this.branches().get(item.sucursal_id)?.activo;
    const options: Operation[] = active
      ? ['entradas', 'salidas', 'ajustes', 'traspasos', 'minimo']
      : ['minimo'];
    return options.filter((action) => mayOperate(action, actor.rol_id, actor.sucursal_id, item));
  });

  ngOnInit() {
    void this.load();
  }
  ngOnDestroy() {
    ++this.listRequest;
    ++this.detailRequest;
  }

  async load() {
    const request = ++this.listRequest;
    this.loading.set(true);
    this.error.set('');
    try {
      const catalog = await this.api.catalog(this.auth.isAdmin());
      if (request !== this.listRequest) return;
      this.inventories.set(catalog.entries);
      this.productList.set(catalog.products);
      this.branchList.set(catalog.branches);
      this.page.set(Math.min(this.page(), Math.max(0, this.pageCount() - 1)));
    } catch (error) {
      if (request === this.listRequest) this.error.set(errorMessage(error));
    } finally {
      if (request === this.listRequest) this.loading.set(false);
    }
  }

  async open(id: number) {
    const request = ++this.detailRequest;
    this.detailId.set(id);
    this.selected.set(null);
    this.action.set(null);
    this.detailLoading.set(true);
    this.detailError.set('');
    try {
      const item = await this.api.get(id);
      if (request === this.detailRequest) this.selected.set(item);
    } catch (error) {
      if (request === this.detailRequest) this.detailError.set(errorMessage(error));
    } finally {
      if (request === this.detailRequest) this.detailLoading.set(false);
    }
  }

  list() {
    ++this.detailRequest;
    this.detailId.set(null);
    this.selected.set(null);
    this.detailError.set('');
    this.action.set(null);
    void this.load();
  }

  async saved(updated: Inventory) {
    this.action.set(null);
    this.selected.set(updated);
    this.detailId.set(updated.id);
    this.revision.update((n) => n + 1);
    await this.load();
  }

  cancelEdit() {
    this.action.set(null);
    if (this.detailId()) void this.open(this.detailId()!);
    void this.load();
  }
}
