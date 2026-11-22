import { FieldIssue } from '../../shared/components/feedback/field-issue';
import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators as V } from '@angular/forms';
import { AdministrationApi, Benefit, Choice } from './administration-api';
import { ReadState, WriteState } from './task-state';
import { Api } from '../../core/http/api';
import { DialogService } from '../../shared/services/dialog';
import { Skeleton, EmptyState } from '../../shared/components/feedback/feedback';
@Component({ imports: [FieldIssue, Skeleton, ReactiveFormsModule], templateUrl: './identity.html' })
export class IdentityPage {
  private api = inject(AdministrationApi);
  private dialogs = inject(DialogService);
  readonly read = new ReadState<boolean>();
  readonly work = new WriteState();
  readonly form = inject(FormBuilder).nonNullable.group({
    nombre: ['', [V.required, V.maxLength(150)]],
    logotipo: ['', V.pattern(/^https?:\/\/.+/i)],
    color: ['#81533b', V.pattern(/^#[0-9a-f]{6}$/i)],
    mensaje: ['', V.maxLength(2000)],
    firma: ['', V.maxLength(300)],
    contacto: ['', V.maxLength(300)],
  });
  ngOnInit() {
    void this.load();
  }
  load() {
    return this.read.load(async () => {
      const v = await this.api.identity();
      if (v) this.form.patchValue({ ...v, logotipo: v.logotipo ?? '' });
      return !!v;
    });
  }
  async save() {
    this.form.markAllAsTouched();
    if (this.form.invalid) return;
    const f = this.form.getRawValue();
    const ok = await this.dialogs.run(
      'Guardar identidad empresarial',
      'Estos datos se utilizarán en la bienvenida de los empleados.',
      async () => {
        await this.api.saveIdentity({ ...f, logotipo: f.logotipo || null });
      },
      'Guardar identidad',
    );
    if (ok) {
      this.work.success('Identidad guardada', f.nombre);
      await this.load();
    }
  }
}
@Component({
  imports: [FieldIssue, Skeleton, EmptyState, ReactiveFormsModule],
  templateUrl: './benefits.html',
})
export class BenefitsPage {
  private api = inject(AdministrationApi);
  private db = inject(Api);
  private dialogs = inject(DialogService);
  readonly work = new WriteState();
  readonly list = new ReadState<Awaited<ReturnType<AdministrationApi['benefits']>>>();
  readonly choices = new ReadState<[Choice[], { id: number; numero_empleado: string }[]]>();
  readonly editing = signal<number | null>(null);
  readonly open = signal(false);
  readonly form = inject(FormBuilder).nonNullable.group({
    nombre: ['', [V.required, V.maxLength(160)]],
    condiciones: ['', V.maxLength(2000)],
    activo: [true],
    inicio: [''],
    fin: [''],
    puesto: ['', V.maxLength(100)],
    sucursal_id: [0],
    empleado_id: [0],
  });
  ngOnInit() {
    void this.load();
  }
  load() {
    return this.list.load(() => this.api.benefits());
  }
  options() {
    return this.choices.load(() =>
      Promise.all([
        this.api.branches(),
        this.db
          .get<{ empleados: { id: number; numero_empleado: string }[] }>('/empleados', {
            solo_activos: false,
          })
          .then((r) => r.empleados),
      ]),
    );
  }
  edit(b?: Benefit & { id: number }) {
    this.editing.set(b?.id ?? null);
    this.open.set(true);
    this.work.error.set('');
    this.form.reset();
    if (b)
      this.form.patchValue({
        ...b,
        puesto: b.puesto ?? '',
        inicio: b.inicio ?? '',
        fin: b.fin ?? '',
        sucursal_id: b.sucursal_id ?? 0,
        empleado_id: b.empleado_id ?? 0,
      });
    void this.options();
  }
  save() {
    this.form.markAllAsTouched();
    if (this.form.invalid) return;
    const f = this.form.getRawValue();
    if (f.inicio && f.fin && f.fin < f.inicio) {
      this.work.error.set('La fecha final debe ser igual o posterior al inicio.');
      return;
    }
    const body = {
      ...f,
      puesto: f.puesto.trim() || null,
      inicio: f.inicio || null,
      fin: f.fin || null,
      sucursal_id: f.sucursal_id || null,
      empleado_id: f.empleado_id || null,
    };
    return this.work.run(async () => {
      const ok = await this.dialogs.run(
        'Guardar beneficio',
        f.activo
          ? 'Se mostrará a los empleados que cumplan las condiciones.'
          : 'Dejará de aparecer entre los beneficios aplicables.',
        async () => {
          await this.api.saveBenefit(body, this.editing() ?? undefined);
        },
        'Guardar',
      );
      if (ok) {
        this.open.set(false);
        this.work.success('Beneficio guardado', f.nombre);
        await this.load();
      }
    });
  }
}
