import { Component, DestroyRef, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AdministrationApi, Batch } from './administration-api';
import { WriteState } from './task-state';
import { Skeleton } from '../../shared/components/feedback/feedback';
import { DialogService } from '../../shared/services/dialog';
@Component({ imports: [FormsModule, Skeleton], templateUrl: './imports-page.html' })
export class ImportsPage {
  private api = inject(AdministrationApi);
  private dialogs = inject(DialogService);
  readonly work = new WriteState();
  readonly batch = signal<Batch | null>(null);
  file: File | null = null;
  batchId: number | null = null;
  page = 0;
  private dead = false;
  private timer?: ReturnType<typeof setTimeout>;
  constructor() {
    inject(DestroyRef).onDestroy(() => {
      this.dead = true;
      clearTimeout(this.timer);
    });
  }
  pick(e: Event) {
    this.file = (e.target as HTMLInputElement).files?.[0] ?? null;
    this.batch.set(null);
    this.batchId = null;
    this.work.error.set('');
    clearTimeout(this.timer);
  }
  preview() {
    if (!this.file) return;
    const f = this.file;
    if (!f.size || f.size > 5242880 || !/\.(csv|xlsx)$/i.test(f.name)) {
      this.work.error.set('Selecciona CSV o XLSX de hasta 5 MiB.');
      return;
    }
    return this.work.run(async () => this.show(await this.api.preview(f)));
  }
  get applyAllowed() {
    return this.batch()?.filas.some((row) => row.estado === 'VALIDA');
  }
  private show(b: Batch, poll = false) {
    if (this.dead) return;
    this.batch.set(b);
    if (!poll) this.batchId = b.id;
    clearTimeout(this.timer);
    if (b.estado === 'CONFIRMADO')
      this.timer = setTimeout(() => {
        if (!this.dead && this.batch()?.id === b.id) this.poll(b.id);
      }, 4000);
  }
  private async poll(id: number) {
    if (this.work.busy()) {
      this.timer = setTimeout(() => this.poll(id), 4000);
      return;
    }
    await this.work.run(async () => {
      const next = await this.api.batch(id);
      if (this.batch()?.id === id) this.show(next, true);
    });
  }
  refresh() {
    if (!this.batchId) return;
    const id = this.batchId;
    return this.work.run(async () => this.show(await this.api.batch(id)));
  }
  async confirm(b: Batch) {
    const ok = await this.dialogs.run(
      'Confirmar importación',
      'Se registrarán las filas válidas y se pondrán sus invitaciones en la cola de correo.',
      async () => {
        await this.api.confirm(b.id);
      },
      'Procesar filas',
    );
    if (ok) {
      this.work.success('Lote confirmado', 'El trabajador procesará los registros.');
      this.batchId = b.id;
      await this.refresh();
    }
  }
  download(id?: number) {
    return this.work.run(async () => {
      const url = URL.createObjectURL(await this.api.csv(id));
      const a = document.createElement('a');
      a.href = url;
      a.download = id ? 'errores-' + id + '.csv' : 'plantilla-empleados.csv';
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
  }
}
