import { FieldIssue } from '../../shared/components/feedback/field-issue';
import { Component, inject, signal } from '@angular/core';
import { FormBuilder, FormsModule, ReactiveFormsModule, Validators as V } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AdministrationApi, Choice, Decision, Profile } from './administration-api';
import { ReadState, WriteState } from './task-state';
import { Skeleton, EmptyState } from '../../shared/components/feedback/feedback';
import { DialogService } from '../../shared/services/dialog';
@Component({
  imports: [FieldIssue, RouterLink, ReactiveFormsModule, Skeleton],
  template: `<section class="page">
    <header>
      <a routerLink="/admin/employees">← Empleados</a>
      <h1>Registrar empleado</h1>
    </header>
    @if (branches.loading()) {
      <dg-skeleton shape="detail" />
    } @else if (branches.error()) {
      <p role="alert">
        {{ branches.error() }} <button class="btn" (click)="load()">Reintentar</button>
      </p>
    } @else if (result(); as r) {
      <article class="panel">
        <h2>{{ r.nombre }} {{ r.apellido }}</h2>
        <p>{{ r.numero_empleado }} · {{ r.sucursal }} · {{ r.estado }}</p>
        <p>La invitación está en la cola de correo para {{ r.email }}.</p>
        <a class="btn" routerLink="/admin/requests">Ver expedientes</a>
      </article>
    } @else {
      <form class="panel" [formGroup]="form" (ngSubmit)="save()">
        <fieldset [disabled]="write.busy()">
          <legend>Datos laborales</legend>
          <div class="form-grid">
            @for (f of fields; track f.key) {
              <label class="field"
                >{{ f.label }} *<input
                  [formControlName]="f.key"
                  [type]="f.key === 'email' ? 'email' : 'text'"
                  required
                  [maxlength]="f.key === 'email' ? 254 : 100" /><dg-field-issue
                  [control]="form.get(f.key)!"
              /></label>
            }
            <label class="field"
              >Sucursal *<select formControlName="sucursal_id" required>
                <option disabled [ngValue]="0">Seleccionar sucursal</option>
                @for (b of branches.data(); track b.id) {
                  <option [ngValue]="b.id">{{ b.nombre }}</option>
                }</select
              ><dg-field-issue [control]="form.controls.sucursal_id"
            /></label>
          </div>
        </fieldset>
        @if (write.error()) {
          <p class="alert-error" role="alert">{{ write.error() }}</p>
        }
        <button class="btn btn-primary" [disabled]="write.busy()">
          {{ write.busy() ? 'Registrando…' : 'Registrar e invitar' }}
        </button>
      </form>
    }
  </section>`,
})
export class HirePage {
  private api = inject(AdministrationApi);
  readonly write = new WriteState();
  readonly branches = new ReadState<Choice[]>();
  readonly result = signal<Profile | null>(null);
  readonly fields = [
    { key: 'nombre', label: 'Nombre' },
    { key: 'apellido', label: 'Apellidos' },
    { key: 'email', label: 'Correo electrónico' },
    { key: 'puesto', label: 'Puesto' },
  ];
  readonly form = inject(FormBuilder).nonNullable.group({
    nombre: ['', V.required],
    apellido: ['', V.required],
    email: ['', [V.email, V.required]],
    puesto: ['', V.required],
    sucursal_id: [0, V.min(1)],
  });
  ngOnInit() {
    void this.load();
  }
  load() {
    return this.branches.load(() => this.api.branches());
  }
  save() {
    this.form.markAllAsTouched();
    if (this.form.invalid) return;
    const body = this.form.getRawValue();
    return this.write.run(async () => {
      const r = await this.api.hire(body, await this.write.intent('empleado', body));
      this.result.set(r);
      this.write.success('Empleado registrado', r.numero_empleado);
    }, this.form);
  }
}
const actions: Record<string, Decision[]> = {
  INVITADO: ['reinvitar', 'revocar'],
  PENDIENTE: ['aprobar', 'correccion', 'rechazar', 'revocar'],
  APROBADO: ['revocar'],
  CORRECCION: ['reinvitar', 'revocar'],
  RECHAZADO: ['reinvitar', 'revocar'],
  REVOCADO: ['reinvitar'],
};
@Component({ imports: [FormsModule, EmptyState, Skeleton], templateUrl: './requests.html' })
export class RequestsPage {
  private api = inject(AdministrationApi);
  private dialog = inject(DialogService);
  readonly list = new ReadState<Profile[]>();
  readonly events = new ReadState<Awaited<ReturnType<AdministrationApi['history']>>>();
  readonly write = new WriteState();
  readonly actions = actions;
  readonly states = Object.keys(actions);
  readonly labels: Record<Decision, string> = {
    aprobar: 'Aprobar',
    rechazar: 'Rechazar',
    correccion: 'Solicitar corrección',
    revocar: 'Revocar',
    reinvitar: 'Reinvitar',
  };
  state = 'PENDIENTE';
  offset = 0;
  readonly selected = signal<Profile | null>(null);
  reason = '';
  ngOnInit() {
    void this.load();
  }
  load() {
    this.selected.set(null);
    return this.list.load(() => this.api.requests(this.state, this.offset));
  }
  select(p: Profile) {
    this.selected.set(p);
    this.reason = '';
    this.write.error.set('');
    return this.events.load(() => this.api.history(p.empleado_id));
  }
  async decide(p: Profile, action: Decision) {
    const reason = this.reason.trim() || null;
    if (!reason && ['rechazar', 'correccion', 'revocar'].includes(action)) {
      this.write.error.set('Indica el motivo de la decisión.');
      return;
    }
    const ok = await this.dialog.run(
      this.labels[action] + ' · ' + p.numero_empleado,
      action === 'revocar'
        ? 'Se bloqueará el acceso del empleado y se conservará su historial.'
        : 'La decisión quedará registrada en el expediente de ' + p.nombre + '.',
      async () => {
        await this.api.decide(
          p.empleado_id,
          action,
          reason,
          await this.write.intent('decision', [p.empleado_id, action, reason]),
        );
      },
      this.labels[action],
      action === 'revocar' || action === 'rechazar',
    );
    if (ok) {
      this.write.success('Expediente actualizado', p.numero_empleado);
      this.write.completed();
      await this.load();
    }
  }
}
