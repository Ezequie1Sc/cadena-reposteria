import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators as V } from '@angular/forms';
import { Skeleton, EmptyState } from '../../shared/components/feedback/feedback';
import { ReadState } from './task-state';
import { Api } from '../../core/http/api';
@Component({
  selector: 'dg-nearby',
  imports: [ReactiveFormsModule, Skeleton, EmptyState],
  template: ` <details class="panel">
    <summary>Sucursales cercanas a una ubicación</summary>
    <form [formGroup]="form" class="toolbar" (ngSubmit)="search()" ngNativeValidate>
      <label class="field"
        >Latitud<input
          type="number"
          required
          min="-90"
          max="90"
          step="any"
          formControlName="latitud"
      /></label>
      <label class="field"
        >Longitud<input
          type="number"
          required
          min="-180"
          max="180"
          step="any"
          formControlName="longitud" /></label
      ><button class="btn" [disabled]="read.loading()">Consultar distancia</button>
    </form>
    @if (read.loading()) {
      <dg-skeleton />
    } @else if (read.error()) {
      <p role="alert">{{ read.error() }}</p>
    } @else if (read.data(); as rows) {
      @for (b of rows; track b.id) {
        <p>
          {{ b.nombre }} · {{ b.distancia_km }} km <small>{{ b.tipo_distancia }}</small>
        </p>
      } @empty {
        <dg-empty
          title="Sin sucursales con coordenadas"
          description="Comprueba la ubicación registrada en las sucursales activas."
        />
      }
    }
  </details>`,
})
export class Nearby {
  private api = inject(Api);
  readonly read = new ReadState<
    { id: number; nombre: string; distancia_km: number; tipo_distancia: string }[]
  >();
  readonly form = inject(FormBuilder).group({
    latitud: [null as number | null, [V.required, V.min(-90), V.max(90)]],
    longitud: [null as number | null, [V.required, V.min(-180), V.max(180)]],
  });
  search() {
    if (!this.form.valid) return;
    return this.read.load(() => this.api.get('/sucursales-cercanas', this.form.getRawValue()));
  }
}
