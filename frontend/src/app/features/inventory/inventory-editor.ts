import { Component, computed, inject, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../core/auth/auth';
import { DialogService } from '../../shared/services/dialog';
import { ToastService } from '../../shared/services/toast.service';
import { WriteState } from '../administration/task-state';
import { InventoryApi } from './inventory-api';
import {
  Inventory,
  NamedRecord,
  Operation,
  Product,
  actionLabels,
  mayOperate,
  validQuantity,
} from './inventory.models';

@Component({
  selector: 'app-inventory-editor',
  imports: [FormsModule],
  templateUrl: './inventory-editor.html',
  styleUrl: './inventory.css',
})
export class InventoryEditor {
  readonly action = input.required<Operation>();
  readonly item = input<Inventory | null>(null);
  readonly inventories = input.required<Inventory[]>();
  readonly branches = input.required<NamedRecord[]>();
  readonly products = input.required<Product[]>();
  readonly close = output<void>();
  readonly saved = output<Inventory>();
  readonly labels = actionLabels;
  readonly amount = signal<number | null>(null);
  readonly branch = signal<number | null>(null);
  readonly product = signal<number | null>(null);
  readonly reason = signal('');
  readonly busy = signal(false);
  readonly uncertain = signal(false);
  readonly error = signal('');
  private intent = new WriteState();
  private readonly auth = inject(AuthService);
  private readonly api = inject(InventoryApi);
  private readonly dialog = inject(DialogService);
  private readonly toast = inject(ToastService);

  readonly destinations = computed(() => {
    const item = this.item();
    if (!item) return [];
    const known = new Set(
      this.inventories()
        .filter((row) => row.producto_id === item.producto_id)
        .map((row) => row.sucursal_id),
    );
    return this.branches().filter((b) => b.activo && b.id !== item.sucursal_id && known.has(b.id));
  });
  readonly availableProducts = computed(() => {
    const existing = new Set(
      this.inventories()
        .filter((row) => row.sucursal_id === this.branch())
        .map((row) => row.producto_id),
    );
    return this.products().filter((p) => p.activo && !existing.has(p.id));
  });
  readonly itemName = computed(() => {
    const item = this.item();
    if (!item) return '';
    const product = this.products().find((p) => p.id === item.producto_id);
    const branch = this.branches().find((b) => b.id === item.sucursal_id);
    return `${product?.nombre ?? 'Producto #' + item.producto_id} · ${branch?.nombre ?? 'Sucursal #' + item.sucursal_id}`;
  });

  ngOnInit() {
    const item = this.item();
    if (this.action() === 'minimo') this.amount.set(item?.stock_minimo ?? 0);
    if (this.action() === 'alta') this.amount.set(0);
  }

  private validate(): string {
    const actor = this.auth.user();
    const action = this.action();
    const item = this.item();
    if (!actor || !mayOperate(action, actor.rol_id, actor.sucursal_id, item))
      return 'Tu cuenta no puede realizar esta operación.';
    if (action === 'alta') {
      if (!this.branches().some((b) => b.activo && b.id === this.branch()))
        return 'Selecciona una sucursal activa.';
      if (!this.availableProducts().some((p) => p.id === this.product()))
        return 'Selecciona un producto sin inventario en esta sucursal.';
    }
    if (action === 'traspasos' && !this.destinations().some((b) => b.id === this.branch())) {
      return 'Selecciona una sucursal con inventario de este producto.';
    }
    if (!validQuantity(action, this.amount(), item?.cantidad ?? 0)) {
      return action === 'ajustes'
        ? 'Indica una existencia final entera, diferente a la actual y mayor o igual a cero.'
        : 'Revisa la cantidad entera y las existencias disponibles.';
    }
    if (action === 'ajustes' && !this.reason().trim()) return 'Indica el motivo del ajuste.';
    if (this.reason().trim().length > 255) return 'El motivo admite hasta 255 caracteres.';
    return '';
  }

  private payload(): Record<string, number | string> {
    const amount = this.amount()!;
    const body: Record<string, number | string> = {};
    if (this.reason().trim()) body['motivo'] = this.reason().trim();
    switch (this.action()) {
      case 'alta':
        return { sucursal_id: this.branch()!, producto_id: this.product()!, stock_minimo: amount };
      case 'minimo':
        return { stock_minimo: amount };
      case 'ajustes':
        return { ...body, cantidad_final: amount };
      case 'traspasos':
        return { ...body, cantidad: amount, sucursal_destino_id: this.branch()! };
      default:
        return { ...body, cantidad: amount };
    }
  }

  explanation(): string {
    const amount = this.amount();
    const available = this.item()?.cantidad ?? 0;
    if (amount === null) return '';
    switch (this.action()) {
      case 'alta': {
        const name = this.products().find((p) => p.id === this.product())?.nombre ?? 'El producto';
        const branch =
          this.branches().find((b) => b.id === this.branch())?.nombre ?? 'la sucursal seleccionada';
        return `${name} comenzará con 0 unidades y mínimo de ${amount} en ${branch}.`;
      }
      case 'minimo':
        return `Se marcará stock bajo cuando haya ${amount} unidades o menos.`;
      case 'ajustes':
        return `Las existencias pasarán de ${available} a ${amount} unidades.`;
      case 'entradas':
        return `Se agregarán ${amount} unidades a las existencias.`;
      case 'salidas':
        return `Se retirarán ${amount} unidades de las existencias.`;
      case 'traspasos': {
        const branch = this.branches().find((b) => b.id === this.branch());
        return `Se retirarán ${amount} unidades del origen y se agregarán a ${branch?.nombre ?? 'la sucursal destino'}.`;
      }
    }
  }

  async submit() {
    if (this.busy() || this.uncertain()) return;
    this.error.set(this.validate());
    if (this.error()) return;
    const action = this.action();
    const body = this.payload();
    const id = this.item()?.id;
    this.busy.set(true);
    let updated: Inventory | undefined;
    try {
      const confirmed = await this.dialog.run(
        this.labels[action],
        [this.itemName(), this.explanation()].filter(Boolean).join('. '),
        async () => {
          if (this.uncertain())
            throw new Error(
              'Cierra la confirmación y comprueba el historial antes de repetir el movimiento.',
            );
          try {
            const key = await this.intent.intent('inventario', [action, id, body]);
            updated = await this.api.apply(action, id, body, key);
            this.intent.completed();
          } catch (error) {
            const status = (error as { status?: number } | null)?.status;
            if (
              (action === 'alta' || action === 'minimo') &&
              (status === 0 || status === undefined || status >= 500)
            )
              this.uncertain.set(true);
            throw error;
          }
        },
        this.labels[action],
        action === 'salidas' || action === 'ajustes' || action === 'traspasos',
      );
      if (confirmed && updated) {
        this.toast.show(
          'success',
          'Inventario actualizado',
          'La operación se registró en la sucursal.',
        );
        this.saved.emit(updated);
      }
    } finally {
      this.busy.set(false);
    }
  }
}
