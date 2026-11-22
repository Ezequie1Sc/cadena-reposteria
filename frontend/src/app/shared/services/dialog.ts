import { Injectable, signal } from '@angular/core';
import { errorMessage } from '../../core/http/api';

interface Confirmation {
  title: string;
  description: string;
  action: () => Promise<void>;
  confirmLabel: string;
  danger: boolean;
  finish: (confirmed: boolean) => void;
}

@Injectable({ providedIn: 'root' })
export class DialogService {
  readonly current = signal<Confirmation | null>(null);
  readonly busy = signal(false);
  readonly error = signal('');

  run(
    title: string,
    description: string,
    action: () => Promise<void>,
    confirmLabel = 'Confirmar',
    danger = false,
  ): Promise<boolean> {
    if (this.current()) return Promise.resolve(false);
    this.error.set('');
    return new Promise((finish) =>
      this.current.set({ title, description, action, confirmLabel, danger, finish }),
    );
  }

  cancel() {
    if (!this.busy()) this.close(false);
  }

  reset() {
    this.close(false);
  }

  async confirm() {
    const dialog = this.current();
    if (!dialog || this.busy()) return;
    this.busy.set(true);
    this.error.set('');
    try {
      await dialog.action();
      if (this.current() === dialog) this.close(true);
    } catch (error) {
      if (this.current() === dialog) this.error.set(errorMessage(error));
    } finally {
      if (this.current() === dialog) this.busy.set(false);
    }
  }

  private close(confirmed: boolean) {
    const dialog = this.current();
    this.current.set(null);
    this.busy.set(false);
    this.error.set('');
    dialog?.finish(confirmed);
  }
}
