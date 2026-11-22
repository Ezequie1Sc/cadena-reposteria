import { Injectable, signal } from '@angular/core';

export type ToastType = 'success' | 'info' | 'warning' | 'error';
interface Toast {
  id: number;
  type: ToastType;
  title: string;
  description: string;
  duration: number;
  closing: boolean;
}
@Injectable({ providedIn: 'root' })
export class ToastService {
  readonly items = signal<Toast[]>([]);
  private sequence = 0;
  private waiting: Toast[] = [];
  private clocks = new Map<
    number,
    {
      remaining: number;
      started: number;
      timer?: ReturnType<typeof setTimeout>;
      holds: Set<string>;
    }
  >();
  show(
    type: ToastType,
    title: string,
    description: string,
    duration = type === 'error' ? 0 : 6500,
  ) {
    if (
      [...this.items(), ...this.waiting].some(
        (t) => !t.closing && t.type === type && t.title === title && t.description === description,
      )
    )
      return;
    this.waiting.push({ id: ++this.sequence, type, title, description, duration, closing: false });
    this.fill();
  }
  clear() {
    for (const c of this.clocks.values()) clearTimeout(c.timer);
    this.clocks.clear();
    this.waiting = [];
    this.items.set([]);
  }
  private fill() {
    while (this.items().length < 3 && this.waiting.length) {
      const t = this.waiting.shift()!;
      this.items.update((a) => [...a, t]);
      if (t.duration > 0) {
        this.clocks.set(t.id, { remaining: t.duration, started: 0, holds: new Set() });
        this.resume(t.id, '');
      }
    }
  }
  pause(id: number, reason: string) {
    const c = this.clocks.get(id);
    if (!c) return;
    c.holds.add(reason);
    if (c.timer !== undefined) {
      clearTimeout(c.timer);
      c.remaining -= Date.now() - c.started;
      c.timer = undefined;
    }
  }
  resume(id: number, reason: string) {
    const c = this.clocks.get(id);
    if (!c) return;
    c.holds.delete(reason);
    if (!c.holds.size && c.timer === undefined) {
      c.started = Date.now();
      c.timer = setTimeout(() => this.dismiss(id), Math.max(0, c.remaining));
    }
  }
  dismiss(id: number) {
    if (!this.items().some((t) => t.id === id && !t.closing)) return;
    clearTimeout(this.clocks.get(id)?.timer);
    this.clocks.delete(id);
    this.items.update((a) => a.map((t) => (t.id === id ? { ...t, closing: true } : t)));
    setTimeout(() => {
      this.items.update((a) => a.filter((t) => t.id !== id));
      this.fill();
    }, 180);
  }
}
