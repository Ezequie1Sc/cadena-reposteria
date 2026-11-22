import { Component, input, inject, signal, output, viewChild } from '@angular/core';
import { AdministrationApi, Photo } from './administration-api';
import { PhotoInput } from './photo-input';
import { WriteState, digest } from './task-state';
import { rememberPhoto } from './photo-receipt';
import { DialogService } from '../../shared/services/dialog';
@Component({
  selector: 'dg-product-photo',
  imports: [PhotoInput],
  template: ` <section class="photo-manager">
    <h3>Fotografía del catálogo</h3>
    @if (url()) {
      <img [src]="url()" alt="Fotografía actual del producto" width="112" height="90" />
    }
    <dg-photo [disabled]="work.busy()" (changed)="file = $event" />
    <div class="actions">
      <button class="btn" [disabled]="!file || work.busy()" (click)="replace()">
        {{ work.busy() ? 'Procesando…' : 'Guardar fotografía' }}
      </button>
      @if (receipt()) {
        <button class="btn" [disabled]="work.busy()" (click)="remove()">Retirar fotografía</button>
      }
    </div>
    @if (work.busy()) {
      <progress max="100" [attr.value]="progress()"></progress>
    }
    @if (work.error()) {
      <p class="alert-error" role="alert">{{ work.error() }}</p>
    }
  </section>`,
})
export class ProductPhoto {
  readonly id = input.required<number>();
  readonly url = input.required<string>();
  readonly updated = output<string>();
  readonly work = new WriteState();
  private picker = viewChild(PhotoInput);
  private api = inject(AdministrationApi);
  private dialog = inject(DialogService);
  file: File | null = null;
  progress = signal<number | null>(null);
  receipt(): Photo | null {
    try {
      const p = JSON.parse(sessionStorage.getItem('dg-photo-' + this.id()) ?? 'null');
      return p?.producto_id === this.id() &&
        p.url === this.url() &&
        Number.isSafeInteger(p.imagen_id)
        ? p
        : null;
    } catch {
      return null;
    }
  }
  replace() {
    if (!this.file) return;
    const f = this.file;
    return this.work.run(async () => {
      const key = await this.work.intent('fotografia', [
        this.id(),
        await digest(await f.arrayBuffer()),
      ]);
      this.progress.set(null);
      const r = await this.api.upload<Photo>(
        '/administracion/productos/' + this.id() + '/imagen',
        f,
        key,
        (n) => this.progress.set(n),
      );
      rememberPhoto(r);
      this.updated.emit(r.url);
      this.work.success('Fotografía actualizada', 'El catálogo ya utiliza la imagen confirmada.');
      this.file = null;
      this.picker()?.clearPreview();
    });
  }
  async remove() {
    const r = this.receipt();
    if (!r) return;
    const ok = await this.dialog.run(
      'Retirar fotografía',
      'El producto quedará sin esta imagen y se programará su limpieza.',
      async () => {
        await this.api.removePhoto(this.id(), r.imagen_id);
      },
      'Retirar',
      true,
    );
    if (ok) {
      this.updated.emit('');
      try {
        sessionStorage.removeItem('dg-photo-' + r.producto_id);
      } catch {}
      this.work.success('Fotografía retirada', 'El servidor confirmó el cambio.');
    }
  }
}
