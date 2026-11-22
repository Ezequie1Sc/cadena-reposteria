import { Skeleton } from '../../../../shared/components/feedback/feedback';
import { NavIcon } from '../../../../shared/components/icon/icon';
import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { errorMessage } from '../../../../core/http/api';
import { DialogService } from '../../../../shared/services/dialog';
import { printTicketHtml } from '../../../commerce/print-ticket';
import { PosCatalog } from '../components/pos-catalog';
import { MethodCode, stockProblem } from '../models/pos';
import { PosCheckout } from '../services/pos-checkout';

@Component({
  selector: 'app-employee-point-of-sale',
  imports: [Skeleton, NavIcon, PosCatalog, RouterLink],
  providers: [PosCheckout],
  templateUrl: './point-of-sale.html',
  styleUrl: './point-of-sale.css',
})
export class PointOfSalePage {
  readonly pos = inject(PosCheckout);
  private readonly dialog = inject(DialogService);
  readonly customer = signal('');
  readonly method = signal<MethodCode | ''>('');
  readonly reference = signal('');
  readonly checked = signal(false);
  readonly reason = signal('');
  readonly articles = computed(() =>
    this.pos.cart().map((line) => ({
      ...line,
      product: this.pos.products().find((p) => p.id === line.producto_id),
    })),
  );
  readonly verificationCopy = computed(() => {
    const code = this.pos
      .methods()
      .find((m) => m.id === this.pos.payment()?.metodo_pago_id)?.codigo;
    if (code === 'EFECTIVO') return 'Conté el efectivo y recibí el importe completo.';
    if (code === 'TARJETA')
      return 'Verifiqué la autorización de la terminal por el importe completo.';
    return 'Verifiqué la recepción del importe completo en el medio de pago correspondiente.';
  });

  ngOnInit(): void {
    void this.pos.init();
  }

  async run(task: () => Promise<void>): Promise<void> {
    if (this.pos.busy()) return;
    this.pos.busy.set(true);
    this.pos.error.set('');
    try {
      await task();
    } catch (error) {
      this.pos.error.set(errorMessage(error));
    } finally {
      this.pos.busy.set(false);
    }
  }

  private async confirmed(
    title: string,
    description: string,
    label: string,
    action: () => Promise<void>,
  ): Promise<void> {
    await this.run(async () => {
      await this.dialog.run(title, description, action, label);
    });
  }

  async submitSale(): Promise<void> {
    const pending = this.pos.state().saleIntent;
    if (pending) {
      await this.run(() => this.pos.createSale(null));
      return;
    }
    const problem = stockProblem(this.pos.cart(), this.pos.stock(), this.pos.products());
    if (problem) {
      this.pos.error.set(problem);
      return;
    }
    const entered = this.customer().trim();
    const id = entered ? Number(entered) : null;
    if (id !== null && (!/^\d+$/.test(entered) || !Number.isSafeInteger(id) || id <= 0)) {
      this.pos.error.set('El identificador de cliente debe ser un entero positivo.');
      return;
    }
    await this.confirmed(
      'Registrar venta',
      this.pos.quantities() +
        ' unidades · ' +
        this.pos.subtotal() +
        ' estimados. Se reservarán las existencias en tu sucursal. El servidor calculará el total definitivo.',
      'Registrar venta',
      () => this.pos.createSale(id),
    );
  }

  pay() {
    return this.run(() => this.pos.registerPayment(this.method(), this.reference()));
  }
  async approve(): Promise<void> {
    const payment = this.pos.payment();
    if (!payment) return;
    await this.confirmed(
      'Confirmar pago #' + payment.id,
      'Se registrará la verificación manual de ' +
        this.pos.price(payment.monto) +
        ' MXN y se confirmará la venta.',
      'Confirmar pago',
      () => this.pos.approve(this.reason(), this.checked()),
    );
  }
  retryCatalog() {
    return this.run(() => this.pos.loadCatalog());
  }
  retryRefresh() {
    return this.run(() => this.pos.refresh());
  }
  retryMethods() {
    return this.run(() => this.pos.loadMethods());
  }
  makeTicket() {
    return this.run(() => this.pos.generateTicket());
  }
  print() {
    return this.run(async () => printTicketHtml(await this.pos.printable()));
  }
  resetPayment() {
    return this.run(async () => {
      this.pos.releaseFailedPayment();
      this.reference.set('');
      this.method.set('');
      this.checked.set(false);
      this.reason.set('');
      await this.pos.loadMethods();
    });
  }
  async finish(): Promise<void> {
    const prepare = async () => {
      await this.pos.finish();
      this.customer.set('');
      this.method.set('');
      this.reference.set('');
      this.checked.set(false);
      this.reason.set('');
    };
    if (this.pos.sale()?.estado === 'PENDIENTE') {
      await this.confirmed(
        'Dejar venta pendiente',
        'La venta #' +
          this.pos.state().saleId +
          ' seguirá reservada. Podrás consultarla en Ventas y continuar su gestión desde Pagos.',
        'Dejar pendiente',
        prepare,
      );
    } else await this.run(prepare);
  }
  viewCart() {
    const element = document.getElementById('pos-cart');
    element?.focus({ preventScroll: true });
    element?.scrollIntoView({ block: 'start' });
  }
}
