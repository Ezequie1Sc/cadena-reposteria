import { InjectionToken } from '@angular/core';

export const API_BASE = new InjectionToken<string>('FastAPI base URL');

export async function loadApiBase(): Promise<string> {
  const response = await fetch(new URL('config.json', document.baseURI), { cache: 'no-store' });
  if (!response.ok) throw new Error('Configuration unavailable');
  const { apiBaseUrl } = await response.json();
  if (typeof apiBaseUrl !== 'string' || !apiBaseUrl.trim()) throw new Error('Missing API address');
  const base = new URL(apiBaseUrl, document.baseURI);
  const local = ['localhost', '127.0.0.1', '[::1]'].includes(base.hostname);
  if (base.protocol !== 'https:' && !(local && base.protocol === 'http:'))
    throw new Error('HTTPS required');
  if (base.username || base.password || base.hash || base.search)
    throw new Error('Invalid API address');
  return base.href.replace(/\/+$/, '');
}
