import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { setTimeout as wait } from 'node:timers/promises';
import { chromium } from 'playwright-core';
import { frontendServer } from './server.mjs';
import { createServer } from 'node:net';

test('Angular + FastAPI real: sesión, catálogo, empleados y denegación por rol', async (t) => {
  const free = createServer();
  await new Promise((ok) => free.listen(0, '127.0.0.1', ok));
  const port = free.address().port;
  await new Promise((ok) => free.close(ok));
  const pass = randomUUID() + 'a9';
  assert.ok(process.env.DG_BACKEND_DIR, 'Define DG_BACKEND_DIR');
  const child = spawn(
    process.env.DG_PYTHON || 'python',
    ['tests/browser/fastapi-fixture.py', process.env.DG_BACKEND_DIR, String(port)],
    {
      env: { ...process.env, DG_FIXTURE_PASSWORD: pass, PYTHONDONTWRITEBYTECODE: '1' },
      stdio: ['ignore', 'ignore', 'pipe'],
    },
  );
  let log = '';
  child.stderr.on('data', (c) => (log += c));
  t.after(() => child.kill());
  process.env.DG_TEST_API = 'http://127.0.0.1:' + port;
  let ready = false;
  for (let i = 0; i < 80; i++) {
    if (child.exitCode !== null) break;
    try {
      ready = (await fetch(process.env.DG_TEST_API + '/health')).ok;
      if (ready) break;
    } catch {}
    await wait(100);
  }
  assert.ok(ready, log);
  const server = await frontendServer();
  t.after(() => server.close());
  const browser = await chromium.launch({
    executablePath: process.env.CHROME_PATH || undefined,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  t.after(() => browser.close());
  const page = await browser.newPage();
  page.setDefaultTimeout(6000);
  await page.goto(server.url + '/login');
  await page.getByLabel('Correo electrónico').fill('user1@example.com');
  await page.locator('input[type=password]').fill(pass);
  await page.getByRole('button', { name: 'Iniciar sesión' }).click();
  await page.waitForURL('**/admin/dashboard');
  await page.locator('aside').getByRole('link', { name: 'Productos', exact: true }).click();
  await page.locator('tbody').getByText('Pastel', { exact: true }).waitFor();
  await page.locator('aside').getByRole('link', { name: 'Empleados', exact: true }).click();
  await page.locator('tbody').getByText('E2', { exact: true }).waitFor();
  const token = await fetch(process.env.DG_TEST_API + '/auth/login', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ email: 'user2@example.com', password: pass }),
  }).then((r) => r.json());
  const denied = await fetch(process.env.DG_TEST_API + '/empleados', {
    headers: { Authorization: 'Bearer ' + token.access_token },
  });
  assert.equal(denied.status, 403);
  assert.equal((await fetch(process.env.DG_TEST_API + '/empleados')).status, 401);
});
