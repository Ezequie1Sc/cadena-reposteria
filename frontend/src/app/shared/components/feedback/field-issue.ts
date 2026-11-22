import { ChangeDetectorRef, Component, effect, inject, input } from '@angular/core';
import { AbstractControl } from '@angular/forms';
@Component({
  selector: 'dg-field-issue',
  template: `@if (control().touched && control().invalid) {
    <small class="validation" role="alert">{{ message() }}</small>
  }`,
})
export class FieldIssue {
  readonly control = input.required<AbstractControl>();
  readonly hint = input('Revisa el formato del campo.');
  constructor() {
    const display = inject(ChangeDetectorRef);
    effect((onCleanup) => {
      const changes = this.control().events.subscribe(() => display.markForCheck());
      onCleanup(() => changes.unsubscribe());
    });
  }
  message() {
    const c = this.control();
    if (c.hasError('server')) return c.getError('server');
    if (c.hasError('required')) return 'Completa este campo.';
    if (c.hasError('email')) return 'Introduce un correo electrónico válido.';
    if (c.hasError('minlength'))
      return 'Mínimo ' + c.getError('minlength').requiredLength + ' caracteres.';
    if (c.hasError('maxlength'))
      return 'Máximo ' + c.getError('maxlength').requiredLength + ' caracteres.';
    if (c.hasError('min'))
      return 'Selecciona un valor igual o mayor que ' + c.getError('min').min + '.';
    if (c.hasError('max')) return 'El máximo es ' + c.getError('max').max + '.';
    return this.hint();
  }
}
