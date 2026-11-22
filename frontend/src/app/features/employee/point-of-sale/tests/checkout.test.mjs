import test from 'node:test';
import assert from 'node:assert/strict';
import { cents, currency, paymentBody, stockProblem } from '../models/pos.ts';
import { CheckoutJournal } from '../services/checkout-journal.ts';

function memoryStorage() {
  const values = new Map();
  return {
    setItem(key, value) {
      values.set(key, value);
    },
    getItem(key) {
      return values.get(key) ?? null;
    },
    removeItem(key) {
      values.delete(key);
    },
  };
}

test('suma importes en centavos sin redondear flotantes ni perder precisión en totales grandes', () => {
  assert.equal(currency(cents('0.10') * 3n + cents('0.20')), '$0.50');
  assert.equal(cents('9999999999.99') * 1234567890n, 1234567889998765432110n);
  assert.throws(() => cents('1.001'));
});

test('el cuerpo de pago conserva el total decimal definitivo y la referencia externa', () => {
  const sale = { id: 41, total: '18.30', estado: 'PENDIENTE' };
  assert.deepEqual(paymentBody(sale, 'SPEI', '  REF-123  '), {
    venta_id: 41,
    metodo: 'SPEI',
    monto: '18.30',
    referencia: 'REF-123',
  });
  assert.deepEqual(paymentBody(sale, 'EFECTIVO', 'texto anterior'), {
    venta_id: 41,
    metodo: 'EFECTIVO',
    monto: '18.30',
  });
  assert.throws(() => paymentBody(sale, 'TARJETA', ''));
  assert.throws(() => paymentBody({ ...sale, estado: 'CANCELADA' }, 'EFECTIVO', ''));
});

test('una intención de venta incierta conserva el mismo UUID y el mismo cuerpo al reabrir la pestaña', () => {
  const storage = memoryStorage();
  const intent = {
    key: crypto.randomUUID(),
    body: { sucursal_id: 4, productos: [{ producto_id: 7, cantidad: 2 }] },
  };
  new CheckoutJournal(storage, 8, 4).save({ saleIntent: intent });
  assert.deepEqual(new CheckoutJournal(storage, 8, 4).read(), { saleIntent: intent });
  assert.deepEqual(new CheckoutJournal(storage, 9, 4).read(), {});
  assert.deepEqual(new CheckoutJournal(storage, 8, 5).read(), {});
});

test('un fallo durante el cobro conserva la venta y la solicitud completa del pago sin registrarla de nuevo', () => {
  const storage = memoryStorage();
  const journal = new CheckoutJournal(storage, 7, 4);
  const intent = {
    key: crypto.randomUUID(),
    body: { venta_id: 21, metodo: 'SPEI', monto: '0.10', referencia: 'REF-123' },
  };
  journal.save({ saleId: 21, paymentIntent: intent });
  assert.deepEqual(new CheckoutJournal(storage, 7, 4).read(), {
    saleId: 21,
    paymentIntent: intent,
  });
  journal.save({ saleId: 21, paymentId: 77 });
  assert.deepEqual(journal.read(), { saleId: 21, paymentId: 77 });
  journal.save({});
  assert.deepEqual(journal.read(), {});
});

test('una operación inconsistente se bloquea y no se convierte en un carrito nuevo', () => {
  const journal = new CheckoutJournal(memoryStorage(), 2, 1);
  journal.save({
    saleId: 1,
    paymentIntent: { key: 'example', body: { venta_id: 2, metodo: 'EFECTIVO', monto: '1.00' } },
  });
  assert.throws(() => journal.read(), /recuperar/);
});

test('validación de stock, producto inactivo y carrito vacío', () => {
  const product = { id: 3, nombre: 'Pastel', activo: true };
  const line = { producto_id: 3, cantidad: 2 };
  assert.equal(stockProblem([line], new Map([[3, 2]]), [product]), undefined);
  assert.match(stockProblem([line], new Map([[3, 1]]), [product]), /1 unidades/);
  assert.match(stockProblem([line], new Map([[3, 2]]), [{ ...product, activo: false }]), /activo/);
  assert.match(stockProblem([], new Map(), []), /al menos/);
});
