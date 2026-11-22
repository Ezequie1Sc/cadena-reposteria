import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  isLowStock,
  stockLabel,
  mayOperate,
  validQuantity,
  movementLabel,
} from './inventory.models.ts';

const entry = { sucursal_id: 12, cantidad: 8, stock_minimo: 8 };

test('Stock bajo incluye el umbral exacto y diferencia agotados', () => {
  assert.equal(isLowStock(entry), true);
  assert.equal(stockLabel(entry), 'Stock bajo');
  assert.equal(stockLabel({ ...entry, cantidad: 0 }), 'Agotado');
  assert.equal(stockLabel({ ...entry, cantidad: 9 }), 'Disponible');
});

test('El empleado solo registra entradas y salidas de su sucursal', () => {
  for (const action of ['entradas', 'salidas']) {
    assert.equal(mayOperate(action, 2, 12, entry), true);
    assert.equal(mayOperate(action, 2, 13, entry), false);
    assert.equal(mayOperate(action, 2, null, entry), false);
    assert.equal(mayOperate(action, 3, 12, entry), false);
  }
  for (const action of ['alta', 'minimo', 'ajustes', 'traspasos']) {
    assert.equal(mayOperate(action, 1, null, entry), true);
    assert.equal(mayOperate(action, 2, 12, entry), false);
  }
});

test('Las salidas y los traspasos validan stock y cantidades enteras', () => {
  for (const action of ['traspasos', 'salidas']) {
    for (const invalid of [0, -1, 1.5, null, 9])
      assert.equal(validQuantity(action, invalid, 8), false);
    assert.equal(validQuantity(action, 8, 8), true);
  }
});

test('Los ajustes permiten cero y las entradas respetan la columna entera', () => {
  assert.equal(validQuantity('ajustes', 0, 8), true);
  assert.equal(validQuantity('ajustes', 8, 8), false);
  assert.equal(validQuantity('minimo', 0, 0), true);
  assert.equal(validQuantity('entradas', 1, 2147483647), false);
  assert.equal(validQuantity('entradas', 1, 0), true);
});

test('Las referencias de traspaso distinguen origen y destino', () => {
  assert.equal(
    movementLabel({ tipo: 'TRASPASO', referencia_tipo: 'INVENTARIO_ORIGEN' }),
    'Entrada por traspaso',
  );
  assert.equal(
    movementLabel({ tipo: 'TRASPASO', referencia_tipo: 'INVENTARIO_DESTINO' }),
    'Salida por traspaso',
  );
});
