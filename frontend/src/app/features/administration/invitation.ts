import { FieldIssue } from '../../shared/components/feedback/field-issue';
import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators as V } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AdministrationApi } from './administration-api';
import { WriteState } from './task-state';
@Component({
  imports: [FieldIssue, ReactiveFormsModule, RouterLink],
  templateUrl: './invitation.html',
})
export class InvitationPage {
  private api = inject(AdministrationApi);
  private token = new URLSearchParams(location.hash.slice(1)).get('token') ?? '';
  private proof = '';
  readonly valid = this.token.length >= 40 && this.token.length <= 100;
  readonly step = signal(1);
  readonly work = new WriteState();
  private fb = inject(FormBuilder).nonNullable;
  readonly code = this.fb.control('', [V.required, V.pattern(/^\d{6}$/)]);
  readonly personal = this.fb.group({
    nombre: ['', [V.required, V.maxLength(100)]],
    apellido: ['', [V.required, V.maxLength(100)]],
    password: [
      '',
      [V.required, V.minLength(12), V.maxLength(128), V.pattern(/^(?=.*\p{L})(?=.*\d).+$/u)],
    ],
  });
  ngOnInit() {
    if (location.hash) history.replaceState(history.state, '', location.pathname + location.search);
  }
  send() {
    return this.work.run(async () => {
      await this.api.code(this.token);
      this.step.set(2);
      this.work.success('Código solicitado', 'Revisa el buzón del correo autorizado.');
    });
  }
  verify() {
    this.code.markAsTouched();
    if (this.code.invalid) return;
    return this.work.run(async () => {
      this.proof = (await this.api.verify(this.token, this.code.value)).comprobante;
      this.code.reset();
      this.step.set(3);
    });
  }
  submit() {
    this.personal.markAllAsTouched();
    if (this.personal.invalid) return;
    return this.work.run(async () => {
      await this.api.submit(this.token, this.proof, this.personal.getRawValue());
      this.token = '';
      this.proof = '';
      this.personal.reset();
      this.step.set(4);
      this.work.success('Solicitud recibida', 'Tu cuenta está pendiente de aprobación.');
    }, this.personal);
  }
}
