import { EmptyState, Skeleton } from '../../shared/components/feedback/feedback';
import { Component, DestroyRef, effect, inject, signal, untracked } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { combineLatest } from 'rxjs';
import { AuthService } from '../../core/auth/auth';
import { errorMessage } from '../../core/http/api';
import { ToastService } from '../../shared/services/toast.service';
import { DialogService } from '../../shared/services/dialog';
import { Task, tasks, transition } from './actions';
import { ActionDialog } from './action-dialog';
import { CommercialApi, initialFilters, pageSize } from './commerce-api';
import {
  Entry,
  EventEntry,
  Method,
  Resource,
  amount,
  dateLabel,
  facts,
  human,
  modules,
  nameOf,
  orderNext,
  stateOf,
} from './models';
import { printTicketHtml } from './print-ticket';

const routeNames: Record<Resource, string> = {
  ventas: 'sales',
  pedidos: 'orders',
  pagos: 'payments',
  tickets: 'tickets',
  facturas: 'invoices',
};

@Component({
  selector: 'app-commerce',
  imports: [EmptyState, Skeleton, FormsModule, RouterLink, ActionDialog],
  templateUrl: './commerce.html',
  styleUrl: './commerce.css',
})
export class CommercePage {
  private readonly dialogs = inject(DialogService);
  async expireSales() {
    await this.dialogs.run(
      'Cancelar ventas vencidas',
      'FastAPI revisará hasta 100 ventas pendientes vencidas de la cadena y liberará sus reservas elegibles.',
      async () => {
        const result = await this.service.api.post<{ ventas_canceladas: number[] }>(
          '/ventas/expirar',
          null,
        );
        this.toast.show(
          'success',
          'Revisión completada',
          result.ventas_canceladas.length + ' ventas canceladas.',
        );
      },
      'Revisar y cancelar',
      true,
    );
  }
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly destroy = inject(DestroyRef);
  private readonly service = inject(CommercialApi);
  private readonly toast = inject(ToastService);
  readonly auth = inject(AuthService);
  readonly resource = signal<Resource>('ventas');
  readonly rows = signal<Entry[]>([]);
  readonly selected = signal<Entry | null>(null);
  readonly history = signal<EventEntry[]>([]);
  readonly methods = signal<Method[]>([]);
  readonly listError = signal('');
  readonly detailError = signal('');
  readonly historyError = signal('');
  readonly methodsLoading = signal(false);
  readonly methodsError = signal('');
  readonly loading = signal(true);
  readonly detailLoading = signal(false);
  readonly historyLoading = signal(false);
  readonly hasHistory = signal(false);
  readonly processing = signal(false);
  readonly task = signal<Task | null>(null);
  readonly total = signal<number | null>(null);
  readonly offset = signal(0);
  readonly more = signal(false);
  readonly modules = modules;
  readonly pageSize = pageSize;
  readonly stateOf = stateOf;
  readonly nameOf = nameOf;
  readonly amount = amount;
  readonly dateLabel = dateLabel;
  readonly human = human;
  readonly facts = facts;
  readonly tasks = tasks;
  readonly next = orderNext;
  draft = initialFilters();
  private applied = initialFilters();
  private listVersion = 0;
  private detailVersion = 0;
  private selectedId: number | null = null;
  private routeReady = false;
  readonly orderNumber = signal('');
  readonly findingOrder = signal(false);
  readonly lookupError = signal('');

  async findOrder() {
    const number = this.orderNumber().trim();
    if (!number || this.findingOrder()) return;
    this.findingOrder.set(true);
    this.lookupError.set('');
    try {
      const order = await this.service.api.get<Entry>(
        '/pedidos/numero/' + encodeURIComponent(number),
      );
      if (!this.destroy.destroyed && this.resource() === 'pedidos') {
        await this.router.navigate(this.url('pedidos'), { queryParams: { id: order.id } });
      }
    } catch (error) {
      this.lookupError.set(errorMessage(error));
    } finally {
      this.findingOrder.set(false);
    }
  }

  constructor() {
    combineLatest([this.route.data, this.route.queryParamMap])
      .pipe(takeUntilDestroyed())
      .subscribe(([data, params]) => {
        const resource = data['resource'] as Resource;
        if (!(resource in modules)) return;
        const changed = !this.routeReady || this.resource() !== resource;
        this.routeReady = true;
        if (changed) {
          this.resource.set(resource);
          this.draft = initialFilters();
          this.applied = initialFilters();
          this.offset.set(0);
          this.task.set(null);
          if (resource === 'pagos') void this.loadMethods();
          void this.refresh();
        }
        const rawId = Number(params.get('id'));
        this.selectedId = Number.isSafeInteger(rawId) && rawId > 0 ? rawId : null;
        void this.reloadDetail();
      });
    let revision = this.service.api.changed();
    effect(() => {
      const next = this.service.api.changed();
      if (next !== revision) {
        revision = next;
        untracked(() => {
          if (this.routeReady) {
            void this.refresh();
            void this.reloadDetail();
          }
        });
      }
    });
  }
  url(r: Resource) {
    return ['/', this.auth.isAdmin() ? 'admin' : 'employee', routeNames[r]];
  }
  async loadMethods() {
    this.methodsLoading.set(true);
    this.methodsError.set('');
    try {
      this.methods.set(await this.service.api.get<Method[]>('/pagos/metodos'));
    } catch (error) {
      this.methodsError.set(errorMessage(error));
    } finally {
      this.methodsLoading.set(false);
    }
  }
  async refresh() {
    const version = ++this.listVersion;
    this.loading.set(true);
    this.listError.set('');
    try {
      const result = await this.service.list(this.resource(), this.applied, this.offset());
      if (version !== this.listVersion || this.destroy.destroyed) return;
      this.rows.set(result.rows);
      this.total.set(result.total);
      this.more.set(result.more);
    } catch (e) {
      if (version === this.listVersion) {
        this.rows.set([]);
        this.more.set(false);
        this.total.set(null);
        this.listError.set(errorMessage(e));
      }
    } finally {
      if (version === this.listVersion) this.loading.set(false);
    }
  }
  async reloadDetail() {
    const id = this.selectedId,
      version = ++this.detailVersion;
    this.detailError.set('');
    this.historyError.set('');
    this.hasHistory.set(false);
    this.history.set([]);
    this.selected.set(null);
    this.detailLoading.set(!!id);
    this.historyLoading.set(false);
    if (!id) return;
    try {
      const result = await this.service.detail(this.resource(), id);
      if (version !== this.detailVersion || this.destroy.destroyed) return;
      this.selected.set(result);
      if (this.resource() !== 'tickets') void this.loadHistory();
    } catch (e) {
      if (this.detailVersion === version) this.detailError.set(errorMessage(e));
    } finally {
      if (version === this.detailVersion) this.detailLoading.set(false);
    }
  }
  async loadHistory() {
    const version = this.detailVersion,
      id = this.selectedId;
    if (!id || this.historyLoading()) return;
    this.historyLoading.set(true);
    this.historyError.set('');
    try {
      const next = await this.service.history(this.resource(), id, this.history().length);
      if (version !== this.detailVersion) return;
      this.history.update((old) => [...old, ...next]);
      this.hasHistory.set(next.length === pageSize);
    } catch (e) {
      if (version === this.detailVersion) this.historyError.set(errorMessage(e));
    } finally {
      if (version === this.detailVersion) this.historyLoading.set(false);
    }
  }
  filter() {
    if (this.draft.desde && this.draft.hasta && this.draft.desde > this.draft.hasta) {
      this.toast.show(
        'warning',
        'Revisa el período',
        'La fecha inicial debe ser anterior o igual a la final.',
      );
      return;
    }
    this.applied = { ...this.draft };
    this.offset.set(0);
    void this.refresh();
  }
  clear() {
    this.draft = initialFilters();
    this.filter();
  }
  page(step: number) {
    this.offset.update((offset) => Math.max(0, offset + step * pageSize));
    void this.refresh();
  }
  close() {
    void this.router.navigate([], { relativeTo: this.route, queryParams: {} });
  }
  canPay(row: Entry) {
    return (
      row.estado === 'PENDIENTE' &&
      (this.resource() === 'pedidos' ||
        (!!row.vence_at && new Date(row.vence_at).getTime() > Date.now()))
    );
  }
  canInvoice(row: Entry) {
    return row.estado === 'CONFIRMADA' && (this.auth.isAdmin() || !!row.cliente_id);
  }
  paymentState(state: string) {
    const title =
      state === 'APROBADO'
        ? 'Confirmar pago'
        : state === 'RECHAZADO'
          ? 'Rechazar pago'
          : 'Cancelar pago';
    this.task.set(
      transition(
        'pago-estado',
        state,
        title,
        state === 'APROBADO'
          ? 'La aprobación registrará el cobro completo y confirmará la venta asociada.'
          : 'Se actualizará el registro del pago y su historial.',
        state !== 'APROBADO',
      ),
    );
  }
  orderState(state: string) {
    this.task.set(
      transition(
        'pedido-estado',
        state,
        state === 'CANCELADO' ? 'Cancelar pedido' : 'Actualizar pedido',
        state === 'CANCELADO'
          ? 'Se cancelará el pedido y se liberarán las existencias reservadas.'
          : 'El nuevo estado quedará registrado en el historial del pedido.',
        state === 'CANCELADO',
      ),
    );
  }
  invoiceState(state: string) {
    this.task.set(
      transition(
        'factura-estado',
        state,
        state === 'EMITIDA' ? 'Registrar emisión externa' : 'Cancelar solicitud',
        state === 'EMITIDA'
          ? 'Acredita el documento fiscal emitido por el proveedor externo.'
          : 'Se cerrará la solicitud fiscal y se conservará su historial.',
        state === 'CANCELADA',
      ),
    );
  }
  async saved(result: { resource: Resource; entry: Entry }) {
    this.task.set(null);
    const title =
      result.resource === 'pagos' && result.entry.estado === 'APROBADO'
        ? 'Pago confirmado'
        : 'Operación registrada';
    this.toast.show(
      'success',
      title,
      nameOf(result.entry, result.resource) + ' · ' + human(stateOf(result.entry)),
    );
    await this.router.navigate(this.url(result.resource), { queryParams: { id: result.entry.id } });
  }
  async ticket(row: Entry) {
    if (this.processing()) return;
    this.processing.set(true);
    try {
      const entry = await this.service.api.post<Entry>('/tickets/venta/' + row.id, {});
      await this.saved({ entry, resource: 'tickets' });
    } catch (e) {
      this.toast.show('error', 'Ticket no disponible', errorMessage(e));
    } finally {
      this.processing.set(false);
    }
  }
  async print(row: Entry) {
    if (this.processing()) return;
    this.processing.set(true);
    try {
      await printTicketHtml(await this.service.api.html('/tickets/' + row.id + '/imprimir'));
    } catch (e) {
      this.toast.show('error', 'No se pudo imprimir', errorMessage(e));
    } finally {
      this.processing.set(false);
    }
  }
  subtitle(row: Entry) {
    switch (this.resource()) {
      case 'ventas':
        return (
          'Sucursal ' + row.sucursal_id + (row.empleado_id ? ' · Empleado ' + row.empleado_id : '')
        );
      case 'pedidos':
        return 'Sucursal ' + row.sucursal_id + ' · Cliente ' + row.cliente_id;
      case 'pagos':
        return (
          'Venta #' +
          row.venta_id +
          ' · ' +
          (this.methods().find((m) => m.id === row.metodo_pago_id)?.nombre ??
            'Método #' + row.metodo_pago_id)
        );
      case 'tickets':
        return row.sucursal_nombre + ' · Venta #' + row.venta?.id;
      case 'facturas':
        return row.razon_social + ' · Venta #' + row.venta_id;
    }
  }
}
