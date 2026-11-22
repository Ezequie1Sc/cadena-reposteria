import { NavIcon } from '../../../../shared/components/icon/icon';
import { Skeleton } from '../../../../shared/components/feedback/feedback';
import { Component, DestroyRef, computed, effect, inject, signal, untracked } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Api, errorMessage } from '../../../../core/http/api';
import { AuthService } from '../../../../core/auth/auth';
import {
  CatalogEntry,
  DashboardData,
  SalesGroup,
  currentDay,
  formatMoney,
  shiftDay,
  startOfDay,
  zone,
} from '../../reports/report-models';

@Component({
  selector: 'app-admin-dashboard',
  imports: [NavIcon, Skeleton, FormsModule, RouterLink],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css',
})
export class DashboardPage {
  readonly auth = inject(AuthService);
  private readonly api = inject(Api);
  readonly summary = signal<DashboardData | null>(null);
  readonly sales = signal<SalesGroup[]>([]);
  readonly productNames = signal<Record<number, string>>({});
  readonly branches = signal<CatalogEntry[]>([]);
  readonly branch = signal('');
  readonly days = signal(7);
  readonly chartBusy = signal(true);
  readonly chartError = signal('');
  readonly chartRetry = signal(0);
  readonly branchBusy = signal(true);
  readonly branchError = signal('');
  private chartId = 0;
  readonly loading = signal(true);
  readonly error = signal('');
  readonly retry = signal(0);
  readonly money = formatMoney;
  readonly dateText = new Intl.DateTimeFormat('es-MX', {
    dateStyle: 'long',
    timeZone: zone,
  }).format(new Date());
  private sequence = 0;
  readonly series = computed(() => {
    const rows = this.sales(),
      count = this.days(),
      today = currentDay();
    const map = new Map(rows.map((r) => [r.grupo.slice(0, 10), r]));
    // La agregación SQL omite los días sin ventas confirmadas, dentro del intervalo consultado.
    return Array.from({ length: count }, (_, i) => {
      const date = shiftDay(today, i + 1 - count),
        data = map.get(date);
      return { date, ventas: data?.ventas ?? 0, total: data?.total ?? '0' };
    });
  });
  readonly max = computed(() => Math.max(1, ...this.series().map((s) => Number(s.total))));
  readonly points = computed(() =>
    this.series()
      .map((s, i, items) => {
        const x = 8 + (i * 584) / Math.max(1, items.length - 1),
          y = 136 - (Number(s.total) / this.max()) * 126;
        return x.toFixed(2) + ',' + y.toFixed(2);
      })
      .join(' '),
  );
  readonly firstDay = computed(() => this.label(this.series()[0].date));
  readonly lastDay = computed(() => this.label(this.series().at(-1)!.date));

  constructor() {
    inject(DestroyRef).onDestroy(() => {
      ++this.sequence;
      ++this.chartId;
    });
    effect(() => {
      this.chartRetry();
      this.api.changed();
      const branch = this.branch(),
        days = this.days();
      untracked(() => void this.loadSales(branch, days));
    });
    effect(() => {
      this.retry();
      this.api.changed();
      const branch = this.branch();
      untracked(() => void this.load(branch));
    });
  }
  label(day: string) {
    return new Intl.DateTimeFormat('es-MX', {
      day: 'numeric',
      month: 'short',
      timeZone: 'UTC',
    }).format(new Date(day + 'T12:00:00Z'));
  }
  private async loadSales(branch: string, days: number) {
    const id = ++this.chartId,
      today = currentDay();
    this.chartBusy.set(true);
    this.chartError.set('');
    try {
      const rows = await this.api.get<SalesGroup[]>('/reportes/ventas', {
        sucursal_id: branch || undefined,
        zona_horaria: zone,
        desde: startOfDay(shiftDay(today, 1 - days)),
        hasta: startOfDay(shiftDay(today, 1)),
        agrupacion: 'dia',
        orden: 'grupo',
        limit: 100,
      });
      if (id === this.chartId) this.sales.set(rows);
    } catch (e) {
      if (id === this.chartId) this.chartError.set(errorMessage(e));
    } finally {
      if (id === this.chartId) this.chartBusy.set(false);
    }
  }
  private async load(branch: string) {
    const id = ++this.sequence;
    this.loading.set(true);
    this.error.set('');
    this.branchBusy.set(true);
    this.branchError.set('');
    void this.api
      .get<{ sucursales: CatalogEntry[] }>('/sucursales', { solo_activos: false })
      .then((r) => {
        if (id === this.sequence) this.branches.set(r.sucursales);
      })
      .catch((e) => {
        if (id === this.sequence) this.branchError.set(errorMessage(e));
      })
      .finally(() => {
        if (id === this.sequence) this.branchBusy.set(false);
      });
    void this.api
      .get<{ productos: CatalogEntry[] }>('/productos', { solo_activos: false })
      .then((r) => {
        if (id === this.sequence)
          this.productNames.set(Object.fromEntries(r.productos.map((p) => [p.id, p.nombre])));
      })
      .catch(() => {
        if (id === this.sequence) this.productNames.set({});
      });
    try {
      const r = await this.api.get<DashboardData>('/reportes/dashboard', {
        sucursal_id: branch || undefined,
        zona_horaria: zone,
      });
      if (id === this.sequence) this.summary.set(r);
    } catch (e) {
      if (id === this.sequence) this.error.set(errorMessage(e));
    } finally {
      if (id === this.sequence) this.loading.set(false);
    }
  }
}
