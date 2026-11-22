import { bootstrapApplication } from '@angular/platform-browser';
import { App } from './app/app';
import { appConfig } from './app/app.config';
import { API_BASE, loadApiBase } from './app/core/config/api-config';

async function start() {
  const base = await loadApiBase();
  await bootstrapApplication(App, {
    providers: [...appConfig.providers, { provide: API_BASE, useValue: base }],
  });
}

start().catch(() => {
  document.body.textContent =
    'No se pudo iniciar DulceGestión. Comprueba la conexión y la dirección de la API en config.json, y vuelve a cargar.';
});
