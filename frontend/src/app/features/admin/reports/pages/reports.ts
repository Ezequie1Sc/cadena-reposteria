import { EmptyState } from '../../../../shared/components/feedback/feedback';
import { Skeleton } from '../../../../shared/components/feedback/feedback';
import { DataTable } from '../../../../shared/components/data-table/data-table';
import { Component, DestroyRef, computed, effect, inject, signal, untracked } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Api, errorMessage } from '../../../../core/http/api';
import {
  CatalogEntry,
  ReportName,
  columnTitles,
  currentDay,
  formatMoney,
  reportColumns,
  reportTitles,
  shiftDay,
  startOfDay,
  zone,
} from '../report-models';

type Cell = string | number | null;
type ReportRow = Record<string, Cell>;
interface Filter {
  name: ReportName;
  branch: string;
  from: string;
  to: string;
  group: string;
  order: string;
  least: boolean;
  paid: boolean;
  low: boolean;
  movement: string;
}
const pageSize = 25;
const initial = (): Filter => ({
  name: 'ventas',
  branch: '',
  from: shiftDay(currentDay(), -29),
  to: currentDay(),
  group: 'dia',
  order: 'grupo',
  least: false,
  paid: false,
  low: false,
  movement: '',
});

@Component({
  selector: 'app-admin-reports',
  imports: [EmptyState, Skeleton, DataTable, FormsModule, RouterLink],
  templateUrl: './reports.html',
  styleUrl: './reports.css',
})
export class ReportsPage {
  private readonly api = inject(Api);
  readonly titles = reportTitles;
  readonly types = Object.keys(reportTitles) as ReportName[];
  readonly columns = reportColumns;
  readonly labels = columnTitles;
  draft = initial();
  readonly applied = signal<Filter>(this.draft);
  readonly rows = signal<ReportRow[]>([]);
  readonly branches = signal<CatalogEntry[]>([]);
  readonly products = signal<Record<number, string>>({});
  readonly page = signal(1);
  readonly hasNext = signal(false);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly formError = signal('');
  readonly headers = computed(() =>
    this.columns[this.applied().name].map((key) => this.labels[key]),
  );
  readonly cells = computed(() =>
    this.rows().map((row) =>
      this.columns[this.applied().name].map((key) => this.format(key, row[key])),
    ),
  );
  private seq = 0;
  constructor() {
    inject(DestroyRef).onDestroy(() => ++this.seq);
    effect(() => {
      const filter = this.applied(),
        page = this.page();
      this.api.changed();
      untracked(() => void this.load(filter, page));
    });
  }
  select(name: ReportName) {
    this.draft = { ...this.applied(), name };
    this.apply();
  }
  apply() {
    this.formError.set('');
    if (
      this.draft.name !== 'inventarios' &&
      this.draft.from &&
      this.draft.to &&
      this.draft.from > this.draft.to
    ) {
      this.formError.set('La fecha final debe ser igual o posterior a la inicial.');
      return;
    }
    this.page.set(1);
    this.applied.set({ ...this.draft });
  }
  async load(filter: Filter = this.applied(), page: number = this.page()) {
    const id = ++this.seq;
    this.error.set('');
    this.loading.set(true);
    const params: Record<string, string | number | boolean | undefined> = {
      sucursal_id: filter.branch || undefined,
      limit: pageSize + 1,
      offset: (page - 1) * pageSize,
    };
    if (filter.name !== 'inventarios') {
      if (filter.from) params['desde'] = startOfDay(filter.from);
      if (filter.to) params['hasta'] = startOfDay(shiftDay(filter.to, 1));
    }
    switch (filter.name) {
      case 'ventas':
        Object.assign(params, {
          agrupacion: filter.group,
          orden: filter.order,
          zona_horaria: zone,
        });
        break;
      case 'productos':
        params['menos_vendidos'] = filter.least;
        break;
      case 'pagos':
        params['solo_confirmados'] = filter.paid;
        break;
      case 'inventarios':
        params['solo_bajo_stock'] = filter.low;
        break;
      case 'movimientos':
        params['tipo'] = filter.movement || undefined;
        break;
    }
    try {
      const [rows, branches, products] = await Promise.all([
        this.api.get<ReportRow[]>('/reportes/' + filter.name, params),
        this.api.get<{ sucursales: CatalogEntry[] }>('/sucursales', { solo_activos: false }),
        ['productos', 'inventarios'].includes(filter.name)
          ? this.api.get<{ productos: CatalogEntry[] }>('/productos', { solo_activos: false })
          : Promise.resolve({ productos: [] as CatalogEntry[] }),
      ]);
      if (id !== this.seq) return;
      this.rows.set(rows.slice(0, pageSize));
      this.hasNext.set(rows.length > pageSize);
      this.branches.set(branches.sucursales);
      this.products.set(Object.fromEntries(products.productos.map((p) => [p.id, p.nombre])));
    } catch (e) {
      if (id === this.seq) {
        this.error.set(errorMessage(e));
        this.rows.set([]);
        this.hasNext.set(false);
      }
    } finally {
      if (id === this.seq) this.loading.set(false);
    }
  }
  format(key: string, value: Cell) {
    if (value === null || value === undefined) return '—';
    if (key === 'total') return formatMoney(value);
    if (key === 'producto_id') return this.products()[Number(value)] ?? 'Producto #' + value;
    if (key === 'sucursal_id' || (key === 'grupo' && this.applied().group === 'sucursal'))
      return this.branches().find((b) => b.id === Number(value))?.nombre ?? 'Sucursal #' + value;
    if (key === 'grupo' && this.applied().group === 'empleado')
      return value === 'EN_LINEA' ? 'En línea' : 'Empleado #' + value;
    if (key === 'grupo' && this.applied().name === 'ventas') return String(value).split(' ')[0];
    if (key === 'created_at' || key === 'updated_at')
      return new Date(value).toLocaleString('es-MX', { timeZone: zone });
    return String(value);
  }
}
