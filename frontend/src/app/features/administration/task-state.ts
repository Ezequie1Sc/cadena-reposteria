import { signal, inject, DestroyRef } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { AbstractControl } from '@angular/forms';
import { AuthService } from '../../core/auth/auth';
import { errorMessage } from '../../core/http/api';
import { ToastService } from '../../shared/services/toast.service';
export class ReadState<T> {
  readonly data = signal<T | null>(null);
  readonly loading = signal(false);
  readonly error = signal('');
  private version = 0;
  constructor() {
    inject(DestroyRef).onDestroy(() => this.version++);
  }
  async load(get: () => Promise<T>) {
    const v = ++this.version;
    this.loading.set(true);
    this.error.set('');
    this.data.set(null);
    try {
      const result = await get();
      if (v === this.version) this.data.set(result);
    } catch (e) {
      if (v === this.version) this.error.set(errorMessage(e));
    } finally {
      if (v === this.version) this.loading.set(false);
    }
  }
}
export async function digest(bytes: ArrayBuffer | Uint8Array<ArrayBuffer>) {
  const hash = await crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(hash), (b) => b.toString(16).padStart(2, '0')).join('');
}
export class WriteState {
  private auth = inject(AuthService);
  private toast = inject(ToastService);
  readonly busy = signal(false);
  readonly error = signal('');
  private storageKey = '';
  private key = '';
  async intent(operation: string, value: unknown) {
    const actor = this.auth.user();
    if (!actor) throw new Error('Vuelve a iniciar sesión.');
    const fingerprint = await digest(new TextEncoder().encode(JSON.stringify(value)));
    const slot = 'dg.intent.' + actor.id + '.' + operation + '.' + fingerprint;
    if (this.storageKey === slot && this.key) return this.key;
    this.storageKey = slot;
    this.key = crypto.randomUUID();
    try {
      this.key = sessionStorage.getItem(slot) || this.key;
      sessionStorage.setItem(slot, this.key);
    } catch {
      /* Sin almacenamiento, se conserva la clave en memoria. */
    }
    return this.key;
  }
  async run(fn: () => Promise<void>, form?: AbstractControl) {
    if (this.busy()) return;
    this.busy.set(true);
    this.error.set('');
    try {
      await fn();
      this.completed();
    } catch (e) {
      this.error.set(errorMessage(e));
      if (
        form &&
        e instanceof HttpErrorResponse &&
        e.status === 422 &&
        Array.isArray(e.error?.detail)
      ) {
        for (const issue of e.error.detail) {
          if (!Array.isArray(issue?.loc) || typeof issue.msg !== 'string') continue;
          const path = issue.loc[0] === 'body' ? issue.loc.slice(1) : issue.loc;
          const field = path.length ? form.get(path) : null;
          if (field) {
            field.setErrors({ ...field.errors, server: issue.msg });
            field.markAsTouched();
          }
        }
      }
    } finally {
      this.busy.set(false);
    }
  }
  completed() {
    if (this.storageKey) {
      try {
        sessionStorage.removeItem(this.storageKey);
      } catch {}
    }
    this.storageKey = '';
    this.key = '';
  }
  success(title: string, detail: string) {
    this.toast.show('success', title, detail);
  }
}
