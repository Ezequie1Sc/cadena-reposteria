import type { Checkout } from '../models/pos';

const positiveId = (id: unknown) => typeof id === 'number' && Number.isSafeInteger(id) && id > 0;

export class CheckoutJournal {
  private readonly name: string;

  private readonly storage: Storage;
  private readonly branchId: number;

  constructor(storage: Storage, userId: number, branchId: number) {
    this.storage = storage;
    this.branchId = branchId;
    this.name = 'dulcegestion.pos.v1.' + userId + '.' + branchId;
  }

  read(): Checkout {
    const raw = this.storage.getItem(this.name);
    if (raw === null) return {};
    const data: Checkout | null = JSON.parse(raw);
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw this.invalid();
    if (data.saleId !== undefined && !positiveId(data.saleId)) throw this.invalid();
    if (data.paymentId !== undefined && (!data.saleId || !positiveId(data.paymentId)))
      throw this.invalid();
    if (data.ticketId !== undefined && (!data.saleId || !positiveId(data.ticketId)))
      throw this.invalid();
    const sale = data.saleIntent;
    if (
      sale &&
      (!sale.key ||
        sale.body?.sucursal_id !== this.branchId ||
        !Array.isArray(sale.body.productos) ||
        !sale.body.productos.length ||
        !sale.body.productos.every((p) => positiveId(p.producto_id) && positiveId(p.cantidad)))
    )
      throw this.invalid();
    const pay = data.paymentIntent;
    if (
      pay &&
      (!pay.key ||
        !data.saleId ||
        pay.body?.venta_id !== data.saleId ||
        !pay.body.metodo ||
        !pay.body.monto)
    )
      throw this.invalid();
    return data;
  }

  save(data: Checkout): void {
    try {
      if (Object.keys(data).length) this.storage.setItem(this.name, JSON.stringify(data));
      else this.storage.removeItem(this.name);
    } catch {
      throw new Error(
        'El navegador no permite conservar la operación. Habilita el almacenamiento de esta pestaña para continuar.',
      );
    }
  }

  private invalid(): Error {
    return new Error(
      'No se pudo recuperar el cobro guardado. Consulta Ventas y Pagos para conciliarlo antes de iniciar otro.',
    );
  }
}
