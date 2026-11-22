import { Skeleton } from '../../shared/components/feedback/feedback';
import {
  AfterViewInit,
  Component,
  ElementRef,
  inject,
  input,
  output,
  signal,
  viewChild,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Api, errorMessage } from '../../core/http/api';
import { AuthService } from '../../core/auth/auth';
import { CommercialApi } from './commerce-api';
import { actionFields, Task } from './actions';
import { Entry, Method, Option, Resource, amount, nameOf } from './models';

@Component({
  selector: 'commerce-action-dialog',
  imports: [Skeleton, FormsModule],
  templateUrl: './action-dialog.html',
  styleUrl: './commerce.css',
})
export class ActionDialog implements AfterViewInit {
  readonly task = input.required<Task>();
  readonly row = input.required<Entry | null>();
  readonly resource = input.required<Resource>();
  readonly dismissed = output<void>();
  readonly saved = output<{ resource: Resource; entry: Entry }>();
  readonly dialog = viewChild.required<ElementRef<HTMLDialogElement>>('dialog');
  private readonly api = inject(Api);
  private readonly commerce = inject(CommercialApi);
  readonly auth = inject(AuthService);
  readonly values: Record<string, string> = {};
  readonly methods = signal<Method[]>([]);
  readonly products = signal<Option[]>([]);
  readonly branches = signal<Option[]>([]);
  readonly lines = signal<{ product: Option; quantity: number }[]>([]);
  readonly ready = signal(false);
  readonly busy = signal(false);
  readonly confirm = signal(false);
  readonly error = signal('');
  readonly amount = amount;
  readonly nameOf = nameOf;
  productId = '';
  quantity = 1;
  fields() {
    return actionFields(this.task(), this.row(), this.auth.isAdmin(), this.methods(), this.values);
  }
  ngAfterViewInit() {
    this.dialog().nativeElement.showModal();
    void this.prepare();
  }
  async prepare() {
    this.ready.set(false);
    this.error.set('');
    try {
      if (this.task().action === 'pagar') {
        const methods = await this.api.get<Method[]>('/pagos/metodos');
        this.methods.set(methods);
        if (!methods.length) throw new Error('No hay métodos de pago activos.');
      }
      if (this.task().action === 'crear-pedido') {
        const [products, branches] = await Promise.all([
          this.api.get<{ productos: Option[] }>('/productos', { solo_activos: true }),
          this.auth.isAdmin()
            ? this.api.get<{ sucursales: Option[] }>('/sucursales', { solo_activos: true })
            : Promise.resolve({ sucursales: [] }),
        ]);
        this.products.set(products.productos);
        this.branches.set(branches.sucursales);
        if (!this.auth.isAdmin() && !this.auth.user()?.sucursal_id)
          throw new Error('La cuenta no tiene una sucursal asignada.');
      }
      this.ready.set(true);
    } catch (e) {
      this.error.set(errorMessage(e));
    }
  }
  addLine() {
    this.error.set('');
    const product = this.products().find((p) => p.id === Number(this.productId));
    if (
      !product ||
      !Number.isInteger(this.quantity) ||
      this.quantity < 1 ||
      this.quantity > 2147483647
    ) {
      this.error.set('Selecciona un producto y una cantidad entera positiva.');
      return;
    }
    if (this.lines().length >= 100 || this.lines().some((line) => line.product.id === product.id)) {
      this.error.set(
        'Agrega hasta 100 productos diferentes. Retira la línea para cambiar su cantidad.',
      );
      return;
    }
    this.lines.update((lines) => [...lines, { product, quantity: this.quantity }]);
    this.productId = '';
    this.quantity = 1;
  }
  removeLine(id: number) {
    this.lines.update((lines) => lines.filter((line) => line.product.id !== id));
  }
  review(form: HTMLFormElement) {
    if (!form.reportValidity()) return;
    if (this.task().action === 'crear-pedido' && !this.lines().length) {
      this.error.set('Agrega al menos un producto al pedido.');
      return;
    }
    if (
      this.values['fecha_emision'] &&
      new Date(this.values['fecha_emision']).getTime() > Date.now()
    ) {
      this.error.set('La fecha de emisión debe corresponder a un documento ya emitido.');
      return;
    }
    this.error.set('');
    this.confirm.set(true);
  }
  cancel(event?: Event) {
    event?.preventDefault();
    if (!this.busy()) this.dismissed.emit();
  }
  async submit() {
    if (this.busy() || !this.confirm()) return;
    this.busy.set(true);
    this.error.set('');
    const task = this.task(),
      row = this.row();
    let resource = this.resource();
    const fields: Record<string, string | number> = {};
    for (const f of this.fields()) {
      const value = this.values[f.name];
      if (f.type === 'checkbox' || !value) continue;
      fields[f.name] =
        f.type === 'number'
          ? Number(value)
          : f.type === 'datetime-local'
            ? new Date(value).toISOString()
            : String(value).trim();
    }
    try {
      let entry: Entry;
      switch (task.action) {
        case 'crear-pedido': {
          resource = 'pedidos';
          const sucursal_id = this.auth.isAdmin()
            ? Number(fields['sucursal_id'])
            : this.auth.user()?.sucursal_id;
          entry = await this.commerce.create(resource, {
            ...fields,
            sucursal_id,
            productos: this.lines().map((l) => ({
              producto_id: l.product.id,
              cantidad: l.quantity,
            })),
          });
          break;
        }
        case 'pagar':
          resource = 'pagos';
          entry = await this.commerce.create(resource, {
            ...fields,
            [this.resource() === 'pedidos' ? 'pedido_id' : 'venta_id']: row!.id,
            monto: row!.total,
          });
          break;
        case 'facturar':
          resource = 'facturas';
          entry = await this.commerce.create(resource, {
            ...fields,
            venta_id: row!.id,
            cliente_id: row!.cliente_id ?? Number(fields['cliente_id']),
          });
          break;
        case 'cancelar-venta':
          entry = await this.api.post<Entry>('/ventas/' + row!.id + '/cancelar', fields);
          break;
        default:
          entry = await this.api.patch<Entry>('/' + resource + '/' + row!.id + '/estado', {
            ...fields,
            estado: task.target,
          });
      }
      this.saved.emit({ resource, entry });
    } catch (e) {
      this.error.set(errorMessage(e));
    } finally {
      this.busy.set(false);
    }
  }
}
