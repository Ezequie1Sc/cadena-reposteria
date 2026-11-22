import { Nearby } from '../../administration/nearby';
import { EmptyState } from '../../../shared/components/feedback/feedback';
import { Skeleton } from '../../../shared/components/feedback/feedback';
import { NavIcon } from '../../../shared/components/icon/icon';
import {
  Component,
  DestroyRef,
  ElementRef,
  ViewChild,
  computed,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import {
  FormsModule,
  ReactiveFormsModule,
  FormControl,
  FormRecord,
  ValidatorFn,
  Validators,
} from '@angular/forms';
import { ProductPhoto } from '../../administration/product-photo';
import { ActivatedRoute, Router } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Api, errorMessage } from '../../../core/http/api';
import { AuthService } from '../../../core/auth/auth';
import { DialogService } from '../../../shared/services/dialog';
import { ToastService } from '../../../shared/services/toast.service';
import {
  CatalogName,
  CatalogRecord,
  Field,
  catalogDefinitions,
  labelFor,
  Scalar,
} from './definitions';

interface CatalogList {
  total: number;
  items?: CatalogRecord[];
  [field: string]: unknown;
}
interface Choice {
  id: number;
  nombre: string;
  activo?: boolean;
}
const size = 20;
const money = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' });
const today = () => new Date().toLocaleDateString('sv-SE');

@Component({
  selector: 'app-admin-catalog',
  imports: [Nearby, EmptyState, Skeleton, ProductPhoto, NavIcon, FormsModule, ReactiveFormsModule],
  templateUrl: './catalog.html',
  styleUrl: './catalog.css',
})
export class CatalogPage {
  private readonly api = inject(Api);
  private readonly router = inject(Router);
  readonly editable = computed(() =>
    this.def().fields.filter(
      (f) =>
        !(this.name() === 'productos' && ['sku', 'imagen_url'].includes(f.key)) &&
        !(this.name() === 'empleados' && ['usuario_id', 'numero_empleado'].includes(f.key)),
    ),
  );
  setPhoto(url: string) {
    this.record.update((r) => (r ? { ...r, imagen_url: url } : r));
  }
  readonly auth = inject(AuthService);
  private readonly dialogs = inject(DialogService);
  private readonly toast = inject(ToastService);
  private readonly route = inject(ActivatedRoute);
  private readonly destroy = inject(DestroyRef);
  @ViewChild('sheet', { static: true }) sheet!: ElementRef<HTMLDialogElement>;

  readonly name = signal<CatalogName>('productos');
  readonly def = computed(() => catalogDefinitions[this.name()]);
  readonly records = signal<CatalogRecord[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly query = signal('');
  readonly active = signal(true);
  readonly paged = computed(() => this.name() === 'usuarios' || this.name() === 'clientes');
  readonly loading = signal(true);
  readonly listError = signal('');
  readonly record = signal<CatalogRecord | null>(null);
  readonly mode = signal<'new' | 'detail' | 'edit'>('detail');
  readonly dialogLoading = signal(false);
  readonly dialogError = signal('');
  readonly saving = signal(false);
  readonly choices = signal<Record<string, Choice[]>>({});
  form = new FormRecord<FormControl<string>>({});
  tomorrowLimit = today();
  private loadId = 0;
  private detailId = 0;
  private searchTimer?: ReturnType<typeof setTimeout>;
  private search = signal('');
  readonly visible = computed(() => {
    if (this.paged()) return this.records();
    const rows = this.records().filter((row) => row.activo === this.active());
    return rows.slice((this.page() - 1) * size, this.page() * size);
  });
  readonly count = computed(() =>
    this.paged()
      ? this.total()
      : this.records().filter((row) => row.activo === this.active()).length,
  );
  readonly pages = computed(() => Math.max(1, Math.ceil(this.count() / size)));

  constructor() {
    this.route.data.pipe(takeUntilDestroyed()).subscribe((data) => {
      this.name.set(data['resource'] as CatalogName);
      clearTimeout(this.searchTimer);
      this.close();
      this.query.set('');
      this.search.set('');
      this.page.set(1);
      this.active.set(true);
    });
    this.destroy.onDestroy(() => {
      clearTimeout(this.searchTimer);
      ++this.detailId;
      ++this.loadId;
    });
    effect(() => {
      this.api.changed();
      this.name();
      this.active();
      this.search();
      if (this.paged()) this.page();
      untracked(() => void this.refresh());
    });
  }

  filter(value: string) {
    this.query.set(value);
    clearTimeout(this.searchTimer);
    this.searchTimer = setTimeout(() => {
      this.page.set(1);
      this.search.set(value.trim());
    }, 280);
  }

  async refresh() {
    const request = ++this.loadId,
      name = this.name();
    const query: Record<string, string | number | boolean> = { solo_activos: this.active() };
    // Solo clientes y usuarios interpretan false como «exclusivamente inactivos».
    if (this.paged()) Object.assign(query, { page: this.page(), page_size: size });
    if (this.search() && name !== 'clientes') query['busqueda'] = this.search();
    this.loading.set(true);
    this.listError.set('');
    try {
      const sources = [...new Set(this.def().fields.flatMap((f) => (f.source ? [f.source] : [])))];
      const [data, lists] = await Promise.all([
        this.api.get<CatalogList>('/' + name, query),
        Promise.all(
          sources.map(async (source) => {
            const result = await this.api.get<Record<string, Choice[]>>(
              '/' + source,
              source === 'roles' ? {} : { solo_activos: false },
            );
            return [source, result[source]] as const;
          }),
        ),
      ]);
      if (request !== this.loadId) return;
      const rows = data[this.paged() ? 'items' : name];
      if (!Array.isArray(rows))
        throw new Error('La API devolvió un formato de catálogo inesperado.');
      this.records.set(rows as CatalogRecord[]);
      this.choices.set(Object.fromEntries(lists));
      this.total.set(data.total);
      this.page.update((p) => Math.min(p, this.pages()));
    } catch (e) {
      if (request === this.loadId) {
        this.listError.set(errorMessage(e));
        this.records.set([]);
        this.total.set(0);
      }
    } finally {
      if (request === this.loadId) this.loading.set(false);
    }
  }

  label(key: string) {
    return labelFor(this.def(), key);
  }
  value(row: CatalogRecord, key: string) {
    const value = row[key];
    if (value === null || value === undefined || value === '') return '—';
    if (key === 'activo') return value ? 'Activo' : 'Inactivo';
    if (key.endsWith('_at')) return new Date(String(value)).toLocaleString('es-MX');
    if (key === 'precio') return money.format(Number(value));
    const source = this.def().fields.find((f) => f.key === key)?.source;
    if (source) return this.choices()[source]?.find((c) => c.id === value)?.nombre ?? '#' + value;
    return String(value);
  }
  nameOf(row: CatalogRecord) {
    return String(row['nombre'] ?? row['numero_empleado'] ?? '#' + row.id);
  }
  keys(row: CatalogRecord) {
    return [
      'id',
      ...this.def()
        .fields.filter((f) => f.kind !== 'password')
        .map((f) => f.key),
      'activo',
      'created_at',
      'updated_at',
    ].filter((k) => k in row);
  }
  options(field: Field) {
    return (this.choices()[field.source!] || []).filter(
      (c) =>
        (c.activo !== false || this.record()?.[field.key] === c.id) &&
        !(field.key === 'rol_id' && c.id === 2 && this.record()?.['rol_id'] !== 2),
    );
  }
  self(row: CatalogRecord | null) {
    return this.name() === 'usuarios' && row?.id === this.auth.user()?.id;
  }

  async open(mode: 'new' | 'detail' | 'edit', row?: CatalogRecord) {
    if (this.saving()) return;
    if (mode === 'new' && (this.name() === 'productos' || this.name() === 'empleados')) {
      await this.router.navigateByUrl(
        this.name() === 'productos' ? '/admin/products/new' : '/admin/employees/new',
      );
      return;
    }
    const request = ++this.detailId;
    this.mode.set(mode);
    this.dialogError.set('');
    this.record.set(null);
    this.dialogLoading.set(!!row);
    this.form = new FormRecord<FormControl<string>>({});
    if (!this.sheet.nativeElement.open) this.sheet.nativeElement.showModal();
    try {
      const record = row
        ? await this.api.get<CatalogRecord>('/' + this.name() + '/' + row.id)
        : null;
      if (request !== this.detailId) return;
      this.record.set(record);
      if (mode !== 'detail') this.buildForm(record);
    } catch (e) {
      if (request === this.detailId) this.dialogError.set(errorMessage(e));
    } finally {
      if (request === this.detailId) this.dialogLoading.set(false);
    }
  }

  private buildForm(row: CatalogRecord | null) {
    for (const field of this.editable()) {
      const checks: ValidatorFn[] = [];
      if (field.required && !(row && field.kind === 'password')) checks.push(Validators.required);
      if (field.minLength) checks.push(Validators.minLength(field.minLength));
      if (field.maxLength) checks.push(Validators.maxLength(field.maxLength));
      if (field.min !== undefined) checks.push(Validators.min(field.min));
      if (field.max !== undefined) checks.push(Validators.max(field.max));
      if (field.pattern) checks.push(Validators.pattern(field.pattern));
      if (field.kind === 'integer') checks.push(Validators.pattern(/^\d+$/));
      if (field.kind === 'decimal') checks.push(Validators.pattern(/^-?\d+(\.\d+)?$/));
      if (field.kind === 'email')
        checks.push(Validators.email, Validators.pattern(/^[^\s@]+@[^\s@]+\.[^\s@]+$/));
      if (field.kind === 'date')
        checks.push((c) => (c.value && c.value > today() ? { future: true } : null));
      if (field.required && field.kind !== 'password')
        checks.push((c) =>
          typeof c.value === 'string' && !c.value.trim() ? { required: true } : null,
        );
      this.form.addControl(
        field.key,
        new FormControl(String(row?.[field.key] ?? ''), { nonNullable: true, validators: checks }),
      );
      if (field.key === 'rol_id' && this.self(row)) this.form.controls[field.key].disable();
    }
  }

  invalid(field: Field) {
    const c = this.form.controls[field.key];
    return c?.touched && c.invalid;
  }
  fieldError(f: Field) {
    const err = this.form.controls[f.key]?.errors;
    if (err?.['required']) return 'Completa este campo.';
    if (err?.['minlength']) return 'Introduce al menos ' + f.minLength + ' caracteres.';
    if (err?.['maxlength']) return 'El máximo es de ' + f.maxLength + ' caracteres.';
    if (f.key === 'precio') return 'Usa hasta diez enteros y dos decimales, por ejemplo 125.50.';
    if (f.kind === 'date') return 'Elige una fecha de nacimiento válida, hasta hoy.';
    if (f.kind === 'email') return 'Introduce un correo electrónico válido.';
    if (f.min !== undefined && f.max !== undefined)
      return 'Introduce un valor entre ' + f.min + ' y ' + f.max + '.';
    return 'Revisa el formato del valor.';
  }
  canSave() {
    return !this.dialogLoading() && Object.keys(this.form.controls).length > 0 && !this.saving();
  }
  close() {
    if (this.saving()) return;
    ++this.detailId;
    this.sheet?.nativeElement.close();
    this.record.set(null);
    this.dialogError.set('');
    this.form.reset();
  }

  async save() {
    if (!this.canSave()) return;
    this.form.markAllAsTouched();
    if (this.form.invalid) return;
    const name = this.name(),
      row = this.record(),
      body: Record<string, Scalar> = {};
    for (const f of this.editable()) {
      const c = this.form.controls[f.key];
      if (c.disabled || (row && !c.dirty)) continue;
      const value = f.kind === 'password' ? c.value : String(c.value ?? '').trim();
      if (!value && (!row || f.kind === 'password')) continue;
      body[f.key] =
        value === '' ? null : f.kind === 'select' || f.kind === 'integer' ? Number(value) : value;
    }
    if (!Object.keys(body).length) {
      this.dialogError.set('Modifica al menos un campo para guardar.');
      return;
    }
    const perform = async () => {
      const result = row
        ? await this.api.patch<CatalogRecord>('/' + name + '/' + row.id, body)
        : await this.api.post<CatalogRecord>('/' + name, body);
      this.record.set(result);
    };
    this.dialogError.set('');
    this.saving.set(true);
    try {
      if (row) {
        const ok = await this.dialogs.run(
          'Guardar cambios en ' + this.nameOf(row),
          'Se actualizarán los datos de ' + this.def().singular + ' en el sistema.',
          perform,
          'Guardar cambios',
        );
        if (!ok) return;
      } else await perform();
      this.saving.set(false);
      this.close();
      this.toast.show(
        'success',
        row ? 'Cambios guardados' : 'Registro creado',
        'El servidor confirmó la operación.',
      );
    } catch (e) {
      this.dialogError.set(errorMessage(e));
    } finally {
      this.saving.set(false);
    }
  }

  async changeState(row: CatalogRecord) {
    const action = row.activo ? 'Desactivar' : 'Reactivar';
    const url = '/' + this.name() + '/' + row.id;
    const ok = await this.dialogs.run(
      action + ' ' + this.nameOf(row),
      row.activo ? this.def().disabledEffect : 'El registro volverá a estar activo.',
      async () => {
        if (row.activo) await this.api.remove(url);
        else await this.api.patch(url + '/reactivar', {});
      },
      action,
      row.activo,
    );
    if (ok)
      this.toast.show(
        'success',
        row.activo ? 'Registro desactivado' : 'Registro reactivado',
        this.nameOf(row),
      );
  }
}
