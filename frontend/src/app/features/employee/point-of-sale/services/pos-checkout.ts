import { HttpErrorResponse } from '@angular/common/http';
import { computed, DestroyRef, inject, Injectable, signal } from '@angular/core';
import { Api, errorMessage } from '../../../../core/http/api';
import { AuthService } from '../../../../core/auth/auth';
import { ToastService } from '../../../../shared/services/toast.service';
import {
  CartLine,
  Category,
  Checkout,
  Inventory,
  Method,
  MethodCode,
  Payment,
  Product,
  Sale,
  Ticket,
  cents,
  currency,
  paymentBody,
  stockProblem,
} from '../models/pos';
import { CheckoutJournal } from './checkout-journal';

@Injectable()
export class PosCheckout {
  private readonly api = inject(Api);
  private readonly auth = inject(AuthService);
  private readonly toast = inject(ToastService);
  private readonly destroy = inject(DestroyRef);
  private journal?: CheckoutJournal;
  readonly branchId = this.auth.user()?.sucursal_id;
  readonly products = signal<Product[]>([]);
  readonly categories = signal<Category[]>([]);
  readonly stock = signal(new Map<number, number>());
  readonly cart = signal<CartLine[]>([]);
  readonly state = signal<Checkout>({});
  readonly sale = signal<Sale | null>(null);
  readonly payment = signal<Payment | null>(null);
  readonly ticket = signal<Ticket | null>(null);
  readonly methods = signal<Method[]>([]);
  readonly busy = signal(false);
  readonly loading = signal(true);
  readonly ready = signal(false);
  readonly error = signal('');
  readonly catalogBusy = signal(false);
  readonly catalogError = signal('');
  readonly methodsLoading = signal(false);
  readonly receiptLoading = signal(false);
  readonly methodError = signal('');
  readonly locked = computed(() => Boolean(this.state().saleIntent || this.state().saleId));
  readonly quantities = computed(() => this.cart().reduce((n, line) => n + line.cantidad, 0));
  readonly subtotal = computed(() => {
    const prices = new Map(this.products().map((p) => [p.id, cents(p.precio)]));
    return currency(
      this.cart().reduce(
        (sum, line) => sum + (prices.get(line.producto_id) ?? 0n) * BigInt(line.cantidad),
        0n,
      ),
    );
  });
  readonly price = (amount: string) => currency(cents(amount));

  async init(): Promise<void> {
    const user = this.auth.user();
    try {
      if (!user || user.rol_id !== 2 || !this.branchId)
        throw new Error('Esta cuenta necesita una sucursal activa para vender.');
      this.journal = new CheckoutJournal(sessionStorage, user.id, this.branchId);
      const persisted = this.journal.read();
      this.state.set(persisted);
      if (persisted.saleIntent) this.cart.set(persisted.saleIntent.body.productos);
      this.ready.set(true);
      await Promise.all([this.loadCatalog(), this.refresh()]);
    } catch (error) {
      this.error.set(errorMessage(error));
    } finally {
      this.loading.set(false);
    }
  }

  async loadCatalog(): Promise<void> {
    this.catalogBusy.set(true);
    this.catalogError.set('');
    try {
      const [products, categories, inventory] = await Promise.all([
        this.api.get<{ productos: Product[] }>('/productos', { solo_activos: true }),
        this.api.get<{ categorias: Category[] }>('/categorias', { solo_activos: true }),
        this.api.get<{ inventarios: Inventory[] }>('/inventarios', { sucursal_id: this.branchId }),
      ]);
      this.products.set(products.productos.filter((product) => product.activo));
      this.categories.set(categories.categorias.filter((category) => category.activo));
      this.stock.set(
        new Map(
          inventory.inventarios
            .filter((row) => row.sucursal_id === this.branchId)
            .map((row) => [row.producto_id, row.cantidad]),
        ),
      );
    } catch (error) {
      this.catalogError.set(errorMessage(error));
    } finally {
      this.catalogBusy.set(false);
    }
  }

  changeQuantity(id: number, delta: number): void {
    if (this.locked() || this.busy() || !this.ready()) return;
    const previous = this.cart();
    const line = previous.find((item) => item.producto_id === id);
    const next = (line?.cantidad ?? 0) + delta;
    if (next <= 0) {
      this.cart.set(previous.filter((item) => item.producto_id !== id));
      return;
    }
    if (delta > 0 && next > (this.stock().get(id) ?? 0)) {
      this.toast.show(
        'warning',
        'Existencias insuficientes',
        'La cantidad solicitada supera el inventario disponible.',
      );
      return;
    }
    if (!line && previous.length >= 100) {
      this.toast.show(
        'warning',
        'Límite de artículos',
        'Cada venta admite hasta 100 productos distintos.',
      );
      return;
    }
    this.cart.set(
      line
        ? previous.map((item) => (item.producto_id === id ? { ...item, cantidad: next } : item))
        : [...previous, { producto_id: id, cantidad: next }],
    );
  }

  private save(next: Checkout): void {
    if (!this.journal) throw new Error('Aún no se puede guardar la operación.');
    if (JSON.stringify(this.journal.read()) !== JSON.stringify(this.state()))
      throw new Error(
        'El cobro cambió en esta pestaña. Vuelve a abrir el punto de venta para recuperarlo.',
      );
    this.journal.save(next);
    this.state.set(next);
  }

  private rejected(error: unknown): boolean {
    // API transaction rolled back. A timeout, server error or key conflict remains locked for replay.
    if (!(error instanceof HttpErrorResponse)) return false;
    return (
      [400, 404, 422].includes(error.status) ||
      (error.status === 409 && !/idempoten|clave|integridad/i.test(errorMessage(error)))
    );
  }

  async createSale(customerId: number | null): Promise<void> {
    if (this.state().saleId || !this.branchId) return;
    let intent = this.state().saleIntent;
    if (!intent) {
      const problem = stockProblem(this.cart(), this.stock(), this.products());
      if (problem) throw new Error(problem);
      if (this.catalogError())
        throw new Error('Actualiza el catálogo antes de registrar la venta.');
      intent = {
        key: crypto.randomUUID(),
        body: {
          sucursal_id: this.branchId,
          productos: [...this.cart()],
          ...(customerId ? { cliente_id: customerId } : {}),
        },
      };
      this.save({ saleIntent: intent });
    }
    let sale: Sale;
    try {
      sale = await this.api.post<Sale>('/ventas', intent.body, intent.key);
    } catch (error) {
      if (this.rejected(error)) {
        this.save({});
        await this.loadCatalog();
      }
      throw error;
    }
    this.save({ saleId: sale.id });
    this.sale.set(sale);
    this.cart.set([]);
    if (this.destroy.destroyed) return;
    this.toast.show(
      'success',
      'Venta registrada',
      'Venta ' + sale.numero_venta + '. Continúa con el cobro.',
    );
    await Promise.all([this.loadMethods(), this.loadCatalog()]);
  }

  async loadMethods(): Promise<void> {
    this.methodsLoading.set(true);
    this.methodError.set('');
    try {
      this.methods.set(await this.api.get<Method[]>('/pagos/metodos'));
    } catch (error) {
      this.methods.set([]);
      this.methodError.set(errorMessage(error));
    } finally {
      this.methodsLoading.set(false);
    }
  }

  async registerPayment(method: MethodCode | '', reference: string): Promise<void> {
    const sale = this.sale();
    if (!sale || this.state().paymentId) return;
    let intent = this.state().paymentIntent;
    if (!intent) {
      if (!method || !this.methods().some((m) => m.codigo === method))
        throw new Error('Elige un método de pago disponible.');
      intent = { key: crypto.randomUUID(), body: paymentBody(sale, method, reference) };
      this.save({ ...this.state(), paymentIntent: intent });
    }
    let payment: Payment;
    try {
      payment = await this.api.post<Payment>('/pagos', intent.body, intent.key);
    } catch (error) {
      if (this.rejected(error)) {
        const { paymentIntent: previousIntent, ...receipt } = this.state();
        this.save(receipt);
        await this.refresh();
      }
      throw error;
    }
    const { paymentIntent: previousIntent, ...receipt } = this.state();
    this.save({ ...receipt, paymentId: payment.id });
    this.payment.set(payment);
    this.toast.show(
      'success',
      'Pago registrado',
      'Estado devuelto por el servidor: ' + payment.estado + '.',
    );
  }

  async approve(reason: string, verified: boolean): Promise<void> {
    const payment = this.payment();
    if (!payment || !verified || reason.trim().length < 3 || reason.trim().length > 500)
      throw new Error('Verifica el importe recibido y escribe el motivo de confirmación.');
    // A lost PATCH response can already have committed. Read the authoritative state before any retry.
    const actual = await this.api.get<Payment>('/pagos/' + payment.id);
    this.payment.set(actual);
    if (actual.estado === 'APROBADO') {
      await this.refresh();
      return;
    }
    if (actual.estado !== 'PENDIENTE' || actual.proveedor !== 'INTERNO')
      throw new Error('Este pago ya no admite confirmación manual.');
    const updated = await this.api.patch<Payment>('/pagos/' + payment.id + '/estado', {
      estado: 'APROBADO',
      motivo: reason.trim(),
    });
    this.payment.set(updated);
    if (updated.estado === 'APROBADO')
      this.toast.show('success', 'Pago confirmado', 'El servidor aprobó el pago.');
    await this.refresh();
  }

  async refresh(): Promise<void> {
    const saved = this.state();
    if (!saved.saleId) return;
    this.receiptLoading.set(true);
    try {
      const [sale, payment, ticket] = await Promise.all([
        this.api.get<Sale>('/ventas/' + saved.saleId),
        saved.paymentId
          ? this.api.get<Payment>('/pagos/' + saved.paymentId)
          : Promise.resolve(null),
        saved.ticketId ? this.api.get<Ticket>('/tickets/' + saved.ticketId) : Promise.resolve(null),
      ]);
      this.sale.set(sale);
      this.payment.set(payment);
      this.ticket.set(ticket);
      if (sale.estado === 'PENDIENTE' && !payment) await this.loadMethods();
    } finally {
      this.receiptLoading.set(false);
    }
  }

  async generateTicket(): Promise<void> {
    const sale = this.sale();
    if (!sale || this.state().ticketId) return;
    const ticket = await this.api.post<Ticket>('/tickets/venta/' + sale.id, null);
    this.save({ ...this.state(), ticketId: ticket.id });
    this.ticket.set(ticket);
    this.toast.show('success', 'Ticket disponible', ticket.numero_ticket);
  }

  async printable(): Promise<string> {
    const id = this.state().ticketId;
    if (!id) throw new Error('Primero genera el ticket.');
    return this.api.html('/tickets/' + id + '/imprimir');
  }

  releaseFailedPayment(): void {
    if (
      !['CANCELADO', 'RECHAZADO', 'VENCIDO'].includes(this.payment()?.estado ?? '') ||
      !this.state().saleId
    )
      return;
    const { paymentId: previousPayment, ...receipt } = this.state();
    this.save(receipt);
    this.payment.set(null);
  }

  async finish(): Promise<void> {
    if (!this.state().saleId || this.state().saleIntent || this.state().paymentIntent)
      throw new Error('Recupera el resultado pendiente antes de iniciar otra venta.');
    this.save({});
    this.sale.set(null);
    this.payment.set(null);
    this.ticket.set(null);
    this.methods.set([]);
    this.cart.set([]);
    this.error.set('');
    await this.loadCatalog();
  }
}
