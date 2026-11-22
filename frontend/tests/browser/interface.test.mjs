import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { chromium } from 'playwright-core';
import { createRequire } from 'node:module';
import { frontendServer } from './server.mjs';
const require = createRequire(import.meta.url);
let browser, server;
before(async () => {
  server = await frontendServer();
  browser = await chromium.launch({
    executablePath: process.env.CHROME_PATH || undefined,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
});
after(async () => {
  await browser?.close();
  await server?.close();
});
const branch = { id: 1, nombre: 'Centro', activo: true };
const person = {
  empleado_id: 15,
  usuario_id: 21,
  numero_empleado: 'EMP-00015',
  nombre: 'Ana',
  apellido: 'López',
  puesto: 'Caja',
  sucursal_id: 1,
  sucursal: 'Centro',
  estado: 'PENDIENTE',
  email: 'ana@example.org',
  creado: '2026-11-20',
  bienvenida_vista: null,
};
const dashboard = {
  ventas_dia: 0,
  ingresos_mes: '0',
  pedidos_pendientes: 0,
  alertas_inventario: 0,
  productos_mas_vendidos: [],
  productos_activos: 0,
  clientes_registrados: 0,
  sucursales_activas: 1,
};
async function setup(t, role = 1, override = () => undefined, width = 1280) {
  const page = await browser.newPage({ viewport: { width, height: 840 }, reducedMotion: 'reduce' });
  t.after(() => page.close());
  page.setDefaultTimeout(4200);
  const calls = [],
    errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  t.after(() => assert.deepEqual(errors, []));
  await page.route('**/api/**', async (route) => {
    const req = route.request(),
      path = new URL(req.url()).pathname.slice(4);
    calls.push({ path, method: req.method(), body: req.postData(), headers: req.headers() });
    const fake = {
      '/auth/login': {
        access_token:
          'test.' +
          Buffer.from(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 1800 })).toString(
            'base64url',
          ) +
          '.test',
        token_type: 'bearer',
      },
      '/auth/me': {
        id: role,
        rol_id: role,
        nombre: 'Prueba',
        apellido: 'Local',
        email: 'qa@example.org',
        activo: true,
        sucursal_id: role === 2 ? 1 : null,
        cliente_id: null,
      },
      '/reportes/dashboard': dashboard,
      '/reportes/ventas': [],
      '/productos': { productos: [], total: 0 },
      '/categorias': { categorias: [branch], total: 1 },
      '/sucursales': { sucursales: [branch, { ...branch, id: 2, nombre: 'Norte' }] },
      '/inventarios': { inventarios: [] },
      '/pagos/metodos': [],
      '/empleado/bienvenida': { pendiente: false },
      '/administracion/solicitudes': [person],
      '/administracion/solicitudes/15/historial': [],
      '/administracion/identidad': null,
      '/administracion/beneficios': [],
      '/empleados': { empleados: [], total: 0 },
    };
    const custom = await override({ path, req, route, calls });
    if (custom === true) return;
    const value = custom ?? {
      status: Object.hasOwn(fake, path) ? 200 : 404,
      json:
        fake[path] ??
        (Object.hasOwn(fake, path) ? null : { detail: 'Ruta de prueba sin respuesta' }),
    };
    await route
      .fulfill({
        status: value.status ?? 200,
        contentType: 'application/json',
        body: JSON.stringify(value.json),
      })
      .catch(() => {});
  });
  return { page, calls };
}
async function login(page) {
  await page.goto(server.url + '/login');
  await page.locator('input[type=email]').fill('qa@example.org');
  await page.locator('input[type=password]').fill('password-de-prueba');
  await page.getByRole('button', { name: 'Iniciar sesión' }).click();
}
async function nav(p, name) {
  await p.locator('aside').getByRole('link', { name, exact: true }).click();
}
async function visible(l) {
  await l.first().waitFor({ state: 'visible' });
}
async function axe(p) {
  await p.addScriptTag({ path: require.resolve('axe-core/axe.min.js') });
  const findings = await p.evaluate(async () =>
    (await window.axe.run(document, { runOnly: ['wcag2a', 'wcag2aa', 'wcag21aa'] })).violations.map(
      (v) => v.id + ': ' + v.nodes[0]?.target,
    ),
  );
  assert.deepEqual(findings, []);
}
test('Guard sin sesión y rechazo de cliente por el perfil real de la sesión', async (t) => {
  const { page } = await setup(t, 3);
  await page.goto(server.url + '/admin/requests');
  await page.waitForURL('**/login');
  await login(page);
  await visible(page.getByRole('alert').filter({ hasText: 'reservado' }));
  assert.match(page.url(), /login$/);
});
test('Alta de producto: skeleton, validación, sucursales, 409, clave de reintento y confirmación', async (t) => {
  let attempts = 0,
    unlock;
  const pending = new Promise((r) => (unlock = r));
  let hold = false;
  const { page, calls } = await setup(t, 1, async ({ path, req }) => {
    if (hold && path === '/categorias') await pending;
    if (path === '/administracion/productos') {
      attempts++;
      return attempts === 1
        ? { status: 409, json: { detail: 'Conflicto de prueba' } }
        : {
            json: {
              producto: { id: 24, sku: 'PROD-00024', nombre: 'Concha' },
              inventarios: JSON.parse(req.postData()).inventarios,
            },
          };
    }
  });
  await login(page);
  await nav(page, 'Productos');
  await visible(page.getByText('Sin resultados en productos'));
  hold = true;
  await page.getByRole('button', { name: 'Nuevo producto' }).click();
  await visible(page.locator('dg-skeleton'));
  unlock();
  await page.getByRole('button', { name: 'Guardar producto' }).click();
  assert.equal(attempts, 0);
  await page.locator('input[formcontrolname=nombre]').fill('Concha');
  await page.getByLabel('Precio (MXN)').fill('18.00');
  await page.getByLabel('Categoría').selectOption({ label: 'Centro' });
  await page.locator('select[formcontrolname=sucursal_id]').selectOption({ label: 'Centro' });
  await page.getByRole('button', { name: 'Agregar sucursal' }).click();
  await page.locator('select[formcontrolname=sucursal_id]').nth(1).selectOption({ label: 'Norte' });
  await page.getByLabel('Existencias iniciales').first().fill('50');
  await page.getByRole('button', { name: 'Guardar producto' }).click();
  await visible(page.locator('.toast.warning'));
  assert.equal(await page.getByLabel('Nombre *', { exact: true }).inputValue(), 'Concha');
  await page.getByRole('button', { name: 'Guardar producto' }).click();
  await visible(page.locator('.toast.success'));
  const sent = calls.filter((c) => c.path === '/administracion/productos');
  assert.equal(sent.length, 2);
  assert.equal(sent[0].headers['idempotency-key'], sent[1].headers['idempotency-key']);
  assert.equal(JSON.parse(sent[1].body).inventarios.length, 2);
  assert.ok(sent[1].headers.authorization.startsWith('Bearer '));
  await visible(page.getByText('SKU asignado'));
  const box = await page.locator('.toast-stack').boundingBox();
  assert.ok(box.y + box.height > 800 && box.y + box.height <= 840);
  const green = await page
    .locator('.toast.success')
    .evaluate((e) => getComputedStyle(e).getPropertyValue('--tone').trim());
  assert.equal(green, '#34714e');
  await page.locator('.toast.success button').click();
  await page.locator('.toast.success').waitFor({ state: 'detached' });
});
test('Expedientes: historial, motivo, confirmación, cancelar y aprobar', async (t) => {
  const { page, calls } = await setup(t, 1, ({ path }) =>
    path.endsWith('/decision') ? { json: { estado: 'APROBADO' } } : undefined,
  );
  await login(page);
  await nav(page, 'Expedientes');
  await page.getByRole('button', { name: 'Revisar', exact: true }).click();
  await visible(page.getByText('Sin eventos registrados.'));
  await page.getByRole('button', { name: 'Revocar', exact: true }).click();
  await visible(page.getByText('Indica el motivo de la decisión.'));
  await page
    .locator('#admin-content')
    .getByRole('button', { name: 'Aprobar', exact: true })
    .click();
  await page.getByRole('button', { name: 'Cancelar', exact: true }).click();
  assert.ok(!calls.some((x) => x.path.endsWith('/decision')));
  await page
    .locator('#admin-content')
    .getByRole('button', { name: 'Aprobar', exact: true })
    .click();
  await page.getByRole('dialog').getByRole('button', { name: 'Aprobar' }).click();
  await visible(page.locator('.toast.success'));
  assert.equal(calls.filter((c) => c.path.endsWith('/decision')).length, 1);
});
test('Invitación pública: fragmento, código, comprobante y envío sin JWT', async (t) => {
  const { page, calls } = await setup(t, 1, ({ path }) =>
    path.startsWith('/incorporacion/')
      ? { json: path.endsWith('verificar') ? { comprobante: 'a'.repeat(43) } : {} }
      : undefined,
  );
  await page.goto(server.url + '/incorporacion#token=' + 'b'.repeat(48));
  await page.getByRole('button', { name: 'Solicitar código' }).click();
  await page.getByLabel('Código recibido').fill('123456');
  await page.getByRole('button', { name: 'Verificar', exact: true }).click();
  await page.getByLabel('Nombre *', { exact: true }).fill('Ana');
  await page.getByLabel('Apellidos').fill('Prueba');
  await page.getByLabel('Crear contraseña').fill('SoloPrueba1234');
  await page.getByRole('button', { name: 'Enviar solicitud' }).click();
  await visible(page.getByRole('heading', { name: 'Solicitud pendiente de aprobación' }));
  assert.ok(!page.url().includes('token='));
  assert.ok(calls.every((c) => !c.headers.authorization));
  assert.equal(JSON.parse(calls.at(-1).body).codigo, 'a'.repeat(43));
});
test('Móvil y tablet: menú por teclado, formularios, sin desbordamiento y accesibilidad', async (t) => {
  const { page } = await setup(t, 1, () => undefined, 390);
  await login(page);
  await visible(page.getByRole('heading', { name: 'Resumen del negocio' }));
  for (const width of [390, 768]) {
    await page.setViewportSize({ width, height: 840 });
    await page.getByRole('button', { name: 'Abrir navegación administrativa' }).press('Enter');
    await page.getByRole('dialog').getByRole('link', { name: 'Beneficios' }).click();
    await visible(page.getByText('Aún no hay beneficios'));
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await axe(page);
  }
});
test('Error 403 conserva la sesión y 401 fuerza un nuevo login', async (t) => {
  let code = 403;
  const { page } = await setup(t, 1, ({ path }) =>
    path === '/administracion/beneficios'
      ? { status: code, json: { detail: 'Acceso denegado' } }
      : undefined,
  );
  await login(page);
  await nav(page, 'Beneficios');
  await visible(page.locator('.toast.warning'));
  code = 401;
  await page.getByRole('button', { name: 'Reintentar' }).click();
  await page.waitForURL('**/login');
  await visible(page.locator('.toast.info'));
});
test('Alta administrativa: matrícula confirmada y únicamente datos laborales', async (t) => {
  const { page, calls } = await setup(t, 1, ({ path }) =>
    path === '/administracion/empleados' ? { json: { ...person, estado: 'INVITADO' } } : undefined,
  );
  await login(page);
  await nav(page, 'Empleados');
  await page.getByRole('button', { name: 'Nuevo empleado' }).click();
  for (const [name, value] of [
    ['Nombre *', 'Ana'],
    ['Apellidos *', 'López'],
    ['Puesto *', 'Caja'],
    ['Correo electrónico *', 'ana@example.org'],
  ])
    await page.getByLabel(name, { exact: true }).fill(value);
  await page.locator('select[formcontrolname=sucursal_id]').selectOption({ label: 'Centro' });
  await page.getByRole('button', { name: 'Registrar e invitar' }).click();
  await visible(page.getByText('EMP-00015 · Centro · INVITADO'));
  const sent = calls.find((x) => x.path === '/administracion/empleados');
  assert.deepEqual(Object.keys(JSON.parse(sent.body)).sort(), [
    'apellido',
    'email',
    'nombre',
    'puesto',
    'sucursal_id',
  ]);
  assert.ok(sent.headers['idempotency-key']);
});
test('Importación: archivo, vista previa, paginación de 401 filas, confirmación y CSV', async (t) => {
  const rows = Array.from({ length: 401 }, (_, i) => ({
    fila: i + 2,
    estado: i ? 'VALIDA' : 'ERROR',
    datos: { email: 'persona' + i + '@example.org' },
    error: i ? null : 'Revisa la sucursal',
  }));
  const batch = { id: 7, estado: 'PREVIO', filas: rows };
  const { page, calls } = await setup(t, 1, ({ path }) => {
    if (path.endsWith('/vista-previa')) return { json: batch };
    if (path.endsWith('/7/confirmar')) return { json: { id: 7, estado: 'CONFIRMADO' } };
    if (path.endsWith('/importaciones/7')) return { json: { ...batch, estado: 'TERMINADO' } };
    if (path.endsWith('/plantilla'))
      return { json: 'nombre,apellido,email,puesto,codigo_sucursal' };
    if (path.endsWith('errores.csv')) return { json: 'fila,error' };
  });
  await login(page);
  await nav(page, 'Importar empleados');
  const plantilla = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Descargar plantilla CSV' }).click();
  assert.equal((await plantilla).suggestedFilename(), 'plantilla-empleados.csv');
  await page.getByLabel('Archivo de empleados').setInputFiles({
    name: 'personal.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from('email,nombre\npersona@example.org,Ana'),
  });
  await page.getByRole('button', { name: 'Validar y previsualizar' }).click();
  await visible(page.getByText('401 filas'));
  assert.equal(await page.locator('tbody tr').count(), 50);
  await page.getByRole('button', { name: 'Siguiente' }).click();
  await visible(page.getByText('persona50@example.org', { exact: true }));
  await page.getByRole('button', { name: 'Confirmar importación' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Procesar filas' }).click();
  await visible(page.getByRole('heading', { name: 'Lote 7 · TERMINADO' }));
  const dl = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Exportar errores' }).click();
  assert.equal((await dl).suggestedFilename(), 'errores-7.csv');
  assert.equal(calls.filter((x) => x.path.endsWith('/confirmar')).length, 1);
});
test('Identidad y beneficio por sucursal: escritura sólo después de confirmar', async (t) => {
  let identity = null;
  let benefits = [];
  const { page, calls } = await setup(t, 1, ({ path, req }) => {
    if (path === '/administracion/identidad') {
      if (req.method() === 'PUT') identity = req.postDataJSON();
      return { json: identity };
    }
    if (path === '/administracion/beneficios/4' && req.method() === 'PUT') {
      benefits = [{ ...req.postDataJSON(), id: 4 }];
      return { json: benefits[0] };
    }
    if (path === '/administracion/beneficios') {
      if (req.method() === 'POST') benefits = [{ ...req.postDataJSON(), id: 4 }];
      return { json: req.method() === 'POST' ? benefits[0] : benefits };
    }
  });
  await login(page);
  await nav(page, 'Identidad empresarial');
  await page.getByLabel('Nombre comercial').fill('Repostería de prueba');
  await page.getByRole('button', { name: 'Guardar identidad' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Guardar identidad' }).click();
  await visible(page.getByText('Identidad guardada'));
  await nav(page, 'Beneficios');
  await page.getByRole('button', { name: 'Nuevo beneficio' }).click();
  await page.locator('input[formcontrolname=nombre]').fill('Beneficio de prueba');
  await page.locator('select[formcontrolname=sucursal_id]').selectOption({ label: 'Norte' });
  await page.getByRole('button', { name: 'Guardar beneficio' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Guardar', exact: true }).click();
  await visible(page.getByText('Beneficio guardado'));
  assert.equal(benefits[0].sucursal_id, 2);
  assert.equal(benefits[0].empleado_id, null);
  assert.equal(calls.filter((c) => c.method === 'PUT').length, 1);
  await page.getByRole('button', { name: 'Editar', exact: true }).click();
  await page.getByLabel('Beneficio activo').uncheck();
  await page.getByRole('button', { name: 'Guardar beneficio' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Guardar', exact: true }).click();
  await visible(page.getByText('Inactivo', { exact: true }));
  assert.equal(benefits[0].activo, false);
});
test('Bienvenida del empleado: beneficios aplicables y acuse confirmado', async (t) => {
  const { page, calls } = await setup(t, 2, ({ path }) =>
    path === '/empleado/bienvenida'
      ? {
          json: {
            pendiente: true,
            empleado: person,
            identidad: null,
            beneficios: [{ nombre: 'Prueba de beneficio', condiciones: 'Condición del ensayo' }],
          },
        }
      : path.endsWith('/vista')
        ? { json: { pendiente: false } }
        : undefined,
  );
  await login(page);
  await visible(page.getByRole('heading', { name: '¡Bienvenido, Ana!' }));
  await visible(page.getByText('Prueba de beneficio · Condición del ensayo'));
  await page.getByRole('button', { name: 'Entendido' }).click();
  await visible(page.getByText('Bienvenida completada'));
  assert.equal(await page.getByRole('button', { name: 'Entendido' }).count(), 0);
  assert.equal(calls.filter((c) => c.path.endsWith('/vista')).length, 1);
});
test('Toasts de error persistentes: deduplicación, límite visible y cola', async (t) => {
  let detail = 'Incidencia 1';
  const { page } = await setup(t, 1, ({ path }) =>
    path === '/administracion/beneficios' ? { status: 422, json: { detail } } : undefined,
  );
  await login(page);
  await nav(page, 'Beneficios');
  const retry = page.getByRole('button', { name: 'Reintentar' });
  await visible(page.locator('.toast.error'));
  await retry.click();
  await visible(retry);
  assert.equal(await page.locator('.toast.error').count(), 1);
  for (let i = 2; i <= 4; i++) {
    detail = 'Incidencia ' + i;
    await retry.click();
    await visible(page.locator('main [role=alert]').filter({ hasText: detail }));
  }
  assert.equal(await page.locator('.toast.error').count(), 3);
  assert.equal(await page.locator('.toast.error i').count(), 0);
  assert.equal(
    await page
      .locator('.toast.error')
      .first()
      .evaluate((e) => getComputedStyle(e).getPropertyValue('--tone').trim()),
    '#a34b43',
  );
  await page.locator('.toast.error button').first().click();
  await visible(page.locator('.toast.error').filter({ hasText: 'Incidencia 4' }));
  assert.equal(await page.locator('.toast.error').count(), 3);
});
test('Fotografía: selección inválida, multipart, reemplazo y retiro con ID de recibo', async (t) => {
  const product = {
    id: 4,
    sku: 'PROD-00004',
    nombre: 'Concha',
    precio: '18.00',
    activo: true,
    categoria_id: 1,
    imagen_url: null,
  };
  const { page, calls } = await setup(t, 1, ({ path, req }) => {
    if (path === '/productos') return { json: { productos: [product], total: 1 } };
    if (path === '/productos/4') return { json: product };
    if (path.endsWith('/4/imagen') && req.method() === 'PUT') {
      product.imagen_url = '/brand.svg';
      return { json: { producto_id: 4, imagen_id: 19, url: product.imagen_url } };
    }
    if (path.endsWith('/4/imagenes/19')) return { json: { retirada: true } };
  });
  await login(page);
  await nav(page, 'Productos');
  await page.getByRole('button', { name: 'Concha', exact: true }).click();
  const file = page.locator('input[type=file]');
  await file.setInputFiles({
    name: 'no.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('invalido'),
  });
  await visible(page.getByText('Selecciona una imagen válida de hasta 5 MiB.'));
  assert.ok(await page.getByRole('button', { name: 'Guardar fotografía' }).isDisabled());
  const png = Buffer.from(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/w8AAgMBgLmFuXcAAAAASUVORK5CYII=',
    'base64',
  );
  await file.setInputFiles({ name: 'concha.png', mimeType: 'image/png', buffer: png });
  await visible(page.getByAltText('Vista previa de la fotografía'));
  await page.getByRole('button', { name: 'Guardar fotografía' }).click();
  await visible(page.getByRole('button', { name: 'Retirar fotografía' }));
  const put = calls.find((c) => c.method === 'PUT');
  assert.equal(put.path, '/administracion/productos/4/imagen');
  assert.match(put.headers['content-type'], /^multipart\/form-data; boundary=/);
  assert.ok(put.headers['idempotency-key']);
  await page.getByRole('button', { name: 'Retirar fotografía' }).click();
  await page.getByRole('button', { name: 'Retirar', exact: true }).click();
  await visible(page.getByText('Fotografía retirada'));
  assert.equal(
    calls.filter((c) => c.method === 'DELETE' && c.path.endsWith('/4/imagenes/19')).length,
    1,
  );
});
test('Inventario de sucursal: entrada confirmada, movimiento y saldo devuelto', async (t) => {
  const product = { id: 4, nombre: 'Concha', sku: 'PROD-00004', activo: true };
  let stock = {
    id: 7,
    sucursal_id: 1,
    producto_id: 4,
    cantidad: 2,
    stock_minimo: 3,
    updated_at: '2026-11-20T12:00:00Z',
  };
  const { page, calls } = await setup(t, 1, ({ path, req }) => {
    if (path === '/productos') return { json: { productos: [product], total: 1 } };
    if (path === '/inventarios') return { json: { inventarios: [stock] } };
    if (path === '/inventarios/7') return { json: stock };
    if (path === '/inventarios/7/movimientos') return { json: { movimientos: [] } };
    if (path === '/inventario-operativo/7/movimiento') {
      stock = { ...stock, cantidad: stock.cantidad + req.postDataJSON().cantidad };
      return { json: { inventario_id: 7, tipo: 'entrada', confirmado: true } };
    }
  });
  await login(page);
  await nav(page, 'Inventario');
  await page.getByRole('button', { name: 'Ver inventario de Concha, Centro' }).click();
  await page.getByRole('button', { name: 'Registrar entrada' }).click();
  await page.getByLabel('Cantidad').fill('9');
  await page.getByRole('button', { name: 'Revisar operación' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Registrar entrada' }).click();
  await visible(page.getByText('Inventario actualizado'));
  await visible(page.getByText('11 unidades'));
  const movement = calls.filter((c) => c.path.includes('inventario-operativo'));
  assert.equal(movement.length, 1);
  assert.equal(JSON.parse(movement[0].body).tipo, 'entrada');
  assert.ok(movement[0].headers['idempotency-key']);
});
test('Avisos temporales: pausa por foco, duración restante y colores ámbar y azul', async (t) => {
  let status = 409;
  const { page } = await setup(t, 1, ({ path }) =>
    path === '/administracion/beneficios'
      ? { status, json: { detail: 'Inventario insuficiente' } }
      : undefined,
  );
  await login(page);
  await page.clock.install();
  await nav(page, 'Beneficios');
  const warn = page.locator('.toast.warning');
  await visible(warn);
  assert.equal(
    await warn.evaluate((e) => getComputedStyle(e).getPropertyValue('--tone').trim()),
    '#8b6223',
  );
  await warn.getByRole('button').focus();
  await page.clock.fastForward(9000);
  assert.ok(await warn.isVisible());
  await page.getByRole('button', { name: 'Reintentar' }).focus();
  await page.mouse.move(2, 2);
  await page.clock.runFor(7000);
  await warn.waitFor({ state: 'detached' });
  status = 401;
  await page.getByRole('button', { name: 'Reintentar' }).click();
  await visible(page.locator('.toast.info'));
  assert.equal(
    await page
      .locator('.toast.info')
      .evaluate((e) => getComputedStyle(e).getPropertyValue('--tone').trim()),
    '#386582',
  );
});
test('422 de FastAPI: error junto al campo y corrección sin perder los otros datos', async (t) => {
  let first = true;
  const { page } = await setup(t, 1, ({ path }) => {
    if (path !== '/administracion/empleados') return;
    if (!first) return { json: person };
    first = false;
    return {
      status: 422,
      json: { detail: [{ loc: ['body', 'puesto'], msg: 'Puesto inválido para este registro' }] },
    };
  });
  await login(page);
  await nav(page, 'Empleados');
  await page.getByRole('button', { name: 'Nuevo empleado' }).click();
  for (const [key, value] of [
    ['Nombre *', 'Ana'],
    ['Apellidos *', 'López'],
    ['Puesto *', 'Caja'],
    ['Correo electrónico *', 'ana@example.org'],
  ])
    await page.getByLabel(key, { exact: true }).fill(value);
  await page.locator('select[formcontrolname=sucursal_id]').selectOption({ label: 'Centro' });
  await page.getByRole('button', { name: 'Registrar e invitar' }).click();
  await visible(
    page.locator('label dg-field-issue').getByText('Puesto inválido para este registro'),
  );
  assert.equal(await page.getByLabel('Nombre *', { exact: true }).inputValue(), 'Ana');
  await page.getByLabel(/Puesto/).fill('Encargada');
  await page.getByRole('button', { name: 'Registrar e invitar' }).click();
  await visible(page.getByText('Empleado registrado'));
});
test('Alta con imagen y stock: un envío multipart reúne fotografía y datos de producto', async (t) => {
  const { page, calls } = await setup(t, 1, ({ path }) =>
    path === '/administracion/productos/con-imagen'
      ? {
          json: {
            producto: { id: 5, sku: 'PROD-00005', nombre: 'Pan' },
            inventarios: [{ id: 4, sucursal_id: 1, cantidad: 7, stock_minimo: 2 }],
            producto_id: 5,
            imagen_id: 8,
            url: '/brand.svg',
          },
        }
      : undefined,
  );
  await login(page);
  await nav(page, 'Productos');
  await page.getByRole('button', { name: 'Nuevo producto' }).click();
  await page.locator('input[formcontrolname=nombre]').fill('Pan');
  await page.getByLabel('Precio (MXN)').fill('25.50');
  await page.getByLabel('Categoría').selectOption({ label: 'Centro' });
  await page.locator('select[formcontrolname=sucursal_id]').selectOption({ label: 'Centro' });
  await page.getByLabel('Existencias iniciales').fill('7');
  await page.getByLabel('Stock mínimo').fill('2');
  await page.locator('input[type=file]').setInputFiles({
    name: 'pan.png',
    mimeType: 'image/png',
    buffer: Buffer.from(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/w8AAgMBgLmFuXcAAAAASUVORK5CYII=',
      'base64',
    ),
  });
  await page.getByRole('button', { name: 'Guardar producto' }).click();
  await visible(page.getByText('PROD-00005', { exact: true }));
  const uploads = calls.filter((c) => c.path === '/administracion/productos/con-imagen');
  assert.equal(uploads.length, 1);
  assert.match(uploads[0].body, /name="archivo"; filename="pan.png"/);
  assert.match(uploads[0].body, /name="datos"/);
  assert.match(uploads[0].body, /"existencias_iniciales":7/);
  assert.equal(calls.filter((c) => c.path === '/administracion/productos').length, 0);
});
test('Sucursal cercana y ventas vencidas: consulta por coordenadas y confirmación de mantenimiento', async (t) => {
  const { page, calls } = await setup(t, 1, ({ path }) =>
    path === '/sucursales-cercanas'
      ? { json: [{ id: 1, nombre: 'Centro', distancia_km: 3.4, tipo_distancia: 'Geodésica' }] }
      : path === '/ventas'
        ? { json: { ventas: [], total: 0 } }
        : path === '/ventas/expirar'
          ? { json: { ventas_canceladas: [11, 12] } }
          : undefined,
  );
  await login(page);
  await nav(page, 'Sucursales');
  await page.getByText('Sucursales cercanas a una ubicación').click();
  await page.getByLabel('Latitud').fill('20.5');
  await page.getByLabel('Longitud').fill('-90');
  await page.getByRole('button', { name: 'Consultar distancia' }).click();
  await visible(page.getByText(/Centro · 3.4 km/));
  await nav(page, 'Ventas');
  await page.getByRole('button', { name: 'Revisar ventas vencidas' }).click();
  assert.equal(calls.filter((c) => c.path === '/ventas/expirar').length, 0);
  await page.getByRole('button', { name: 'Revisar y cancelar' }).click();
  await visible(page.getByText('2 ventas canceladas.'));
  assert.equal(calls.filter((c) => c.path === '/ventas/expirar').length, 1);
});
test('Recorrido móvil administrativo: 15 módulos, teclado, contenido y ancho disponible', async (t) => {
  const extra = {
    '/roles': { roles: [] },
    '/usuarios': { items: [], total: 0 },
    '/clientes': { items: [], total: 0 },
    '/ventas': { ventas: [], total: 0 },
    '/pedidos': { pedidos: [], total: 0 },
    '/pagos': { pagos: [], total: 0 },
    '/tickets': [],
    '/facturas': [],
  };
  const { page } = await setup(
    t,
    1,
    ({ path }) => (Object.hasOwn(extra, path) ? { json: extra[path] } : undefined),
    390,
  );
  await login(page);
  await visible(page.getByRole('heading', { name: 'Resumen del negocio' }));
  for (const name of [
    'Productos',
    'Categorías',
    'Sucursales',
    'Inventario',
    'Empleados',
    'Clientes',
    'Usuarios',
    'Pedidos',
    'Ventas',
    'Pagos',
    'Tickets',
    'Facturas',
    'Reportes',
    'Importar empleados',
    'Expedientes',
  ]) {
    await page.getByRole('button', { name: 'Abrir navegación administrativa' }).press('Enter');
    await page.getByRole('dialog').getByRole('link', { name, exact: true }).click();
    await visible(page.locator('main h1'));
    await page.waitForFunction(() => document.querySelectorAll('main dg-skeleton').length === 0);
    assert.ok(
      await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      name + ' desborda la pantalla',
    );
    assert.equal(await page.locator('.toast.error').count(), 0, name);
  }
});
test('Accesibilidad de acceso y POS móvil y escritorio con axe-core', async (t) => {
  const { page } = await setup(t, 2, () => undefined, 390);
  await page.goto(server.url + '/login');
  await axe(page);
  await login(page);
  await visible(page.getByText('Catálogo vacío'));
  for (const width of [390, 1280]) {
    await page.setViewportSize({ width, height: 840 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await axe(page);
  }
});
