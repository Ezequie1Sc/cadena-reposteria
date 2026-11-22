import { rememberPhoto } from './photo-receipt';
import { FieldIssue } from '../../shared/components/feedback/field-issue';
import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators as V } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AdministrationApi, Created, Photo } from './administration-api';
import { PhotoInput } from './photo-input';
import { ReadState, WriteState, digest } from './task-state';
import { Skeleton } from '../../shared/components/feedback/feedback';
@Component({
  imports: [FieldIssue, ReactiveFormsModule, RouterLink, PhotoInput, Skeleton],
  templateUrl: './product-entry.html',
})
export class ProductEntry {
  private api = inject(AdministrationApi);
  private fb = inject(FormBuilder).nonNullable;
  readonly options = new ReadState<Awaited<ReturnType<ProductEntry['choices']>>>();
  readonly write = new WriteState();
  readonly progress = signal<number | null>(null);
  file: File | null = null;
  invalidPhoto = false;
  readonly form = this.fb.group({
    nombre: ['', [V.required, V.minLength(2), V.maxLength(150)]],
    precio: ['', [V.required, V.pattern(/^\d{1,10}(\.\d{1,2})?$/)]],
    categoria_id: [0, V.min(1)],
    descripcion: ['', V.maxLength(4000)],
    inventarios: this.fb.array([this.stock()]),
  });
  stock() {
    const qty = [V.required, V.min(0), V.max(2147483647), V.pattern(/^\d+$/)];
    return this.fb.group({
      sucursal_id: [0, V.min(1)],
      existencias_iniciales: [0, qty],
      stock_minimo: [0, qty],
    });
  }
  choices() {
    return Promise.all([this.api.categories(), this.api.branches()] as const);
  }
  load() {
    return this.options.load(() => this.choices());
  }
  ngOnInit() {
    void this.load();
  }
  readonly created = signal<Created | null>(null);
  save() {
    this.form.markAllAsTouched();
    if (this.form.invalid || this.invalidPhoto) return;
    const v = this.form.getRawValue();
    if (new Set(v.inventarios.map((i) => i.sucursal_id)).size !== v.inventarios.length) {
      this.write.error.set('Selecciona una sucursal diferente en cada fila.');
      return;
    }
    const body = { ...v, nombre: v.nombre.trim(), descripcion: v.descripcion.trim() || null };
    return this.write.run(async () => {
      const key = await this.write.intent('producto', [
        body,
        this.file ? await digest(await this.file.arrayBuffer()) : null,
      ]);
      this.progress.set(null);
      const r = this.file
        ? await this.api.upload<Created & Photo>(
            '/administracion/productos/con-imagen',
            this.file,
            key,
            (n) => this.progress.set(n),
            body,
          )
        : await this.api.createProduct(body, key);
      if ('imagen_id' in r) rememberPhoto(r as Created & Photo);
      this.created.set(r);
      this.write.success('Producto creado', r.producto.nombre + ' · ' + r.producto.sku);
    }, this.form);
  }
}
