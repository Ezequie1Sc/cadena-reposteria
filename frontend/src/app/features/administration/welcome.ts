import { Component, inject } from '@angular/core';
import { AdministrationApi, Welcome } from './administration-api';
import { ReadState, WriteState } from './task-state';
import { Skeleton } from '../../shared/components/feedback/feedback';
@Component({
  selector: 'dg-welcome',
  imports: [Skeleton],
  template: ` @if (read.loading()) {
      <dg-skeleton shape="detail" />
    } @else if (read.error()) {
      <p role="alert">
        Bienvenida: {{ read.error() }} <button class="btn" (click)="load()">Reintentar</button>
      </p>
    } @else if (read.data(); as w) {
      @if (w.pendiente && w.empleado; as e) {
        <section class="panel welcome" [style.border-left-color]="w.identidad?.color">
          @if (w.identidad?.logotipo) {
            <img [src]="w.identidad.logotipo" alt="" height="40" />
          }
          <h2>¡Bienvenido, {{ e.nombre }}!</h2>
          <p>{{ w.identidad?.mensaje }}</p>
          <strong>{{ e.puesto }} · {{ e.sucursal }} · {{ e.numero_empleado }}</strong>
          @if (w.beneficios?.length) {
            <h3>Tus beneficios</h3>
            <ul>
              @for (b of w.beneficios; track $index) {
                <li>{{ b.nombre }} · {{ b.condiciones }}</li>
              }
            </ul>
          }
          @if (work.error()) {
            <p role="alert">{{ work.error() }}</p>
          }
          <button class="btn btn-primary" [disabled]="work.busy()" (click)="ack()">
            Entendido
          </button>
        </section>
      }
    }`,
})
export class WelcomeBanner {
  private api = inject(AdministrationApi);
  readonly read = new ReadState<Welcome>();
  readonly work = new WriteState();
  ngOnInit() {
    void this.load();
  }
  load() {
    return this.read.load(() => this.api.welcome());
  }
  ack() {
    return this.work.run(async () => {
      await this.api.acknowledge();
      this.read.data.set({ pendiente: false });
      this.work.success('Bienvenida completada', 'Tu confirmación quedó registrada.');
    });
  }
}
