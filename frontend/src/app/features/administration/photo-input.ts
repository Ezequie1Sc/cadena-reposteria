import { Component, signal, output, OnDestroy, input } from '@angular/core';
import { NavIcon } from '../../shared/components/icon/icon';
@Component({
  selector: 'dg-photo',
  imports: [NavIcon],
  template: ` <div class="photo-drop" (dragover)="$event.preventDefault()" (drop)="drop($event)">
    @if (preview()) {
      <img [src]="preview()" alt="Vista previa de la fotografía" />
    } @else {
      <dg-icon name="cake" [size]="32" />
    }
    <label class="field"
      >Fotografía del producto<input
        type="file"
        accept="image/jpeg,image/png,image/webp"
        [disabled]="disabled()"
        (change)="pick($event)"
    /></label>
    <small>Arrastra una fotografía JPG, PNG o WebP de hasta 5 MiB.</small>
    @if (preview() || error()) {
      <button type="button" class="btn" [disabled]="disabled()" (click)="choose(null)">
        Quitar selección
      </button>
    }
    @if (error()) {
      <span role="alert">{{ error() }}</span>
    }
  </div>`,
})
export class PhotoInput implements OnDestroy {
  readonly invalid = output<boolean>();
  readonly disabled = input(false);
  readonly changed = output<File | null>();
  readonly preview = signal('');
  readonly error = signal('');
  choose(f: File | null) {
    if (this.disabled()) return;
    this.error.set('');
    if (
      f &&
      (!['image/jpeg', 'image/png', 'image/webp'].includes(f.type) || f.size > 5242880 || !f.size)
    ) {
      this.error.set('Selecciona una imagen válida de hasta 5 MiB.');
      URL.revokeObjectURL(this.preview());
      this.preview.set('');
      this.changed.emit(null);
      this.invalid.emit(true);
      return;
    }
    URL.revokeObjectURL(this.preview());
    this.preview.set(f ? URL.createObjectURL(f) : '');
    this.invalid.emit(false);
    this.changed.emit(f);
  }
  clearPreview() {
    URL.revokeObjectURL(this.preview());
    this.preview.set('');
    this.error.set('');
  }
  pick(e: Event) {
    const input = e.target as HTMLInputElement;
    this.choose(input.files?.[0] ?? null);
    input.value = '';
  }
  drop(e: DragEvent) {
    e.preventDefault();
    if (e.dataTransfer?.files[0]) this.choose(e.dataTransfer.files[0]);
  }
  ngOnDestroy() {
    URL.revokeObjectURL(this.preview());
  }
}
