import { NavIcon } from '../../../shared/components/icon/icon';
import { Component, DestroyRef, inject, signal } from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { HttpErrorResponse } from '@angular/common/http';
import { Router } from '@angular/router';
import { AuthService } from '../../../core/auth/auth';
import { errorMessage } from '../../../core/http/api';

@Component({
  selector: 'app-login',
  imports: [NavIcon, ReactiveFormsModule],
  templateUrl: './login.html',
  styleUrl: './login.css',
})
export class LoginPage {
  readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  readonly busy = signal(false);
  readonly visible = signal(false);
  readonly error = signal('');
  readonly form = inject(FormBuilder).nonNullable.group({
    email: ['', [Validators.required, Validators.email, Validators.maxLength(254)]],
    password: ['', [Validators.required, Validators.maxLength(128)]],
  });

  readonly retrySeconds = signal(0);
  private timer?: ReturnType<typeof setInterval>;

  constructor() {
    inject(DestroyRef).onDestroy(() => clearInterval(this.timer));
  }

  private respectLimit(error: unknown) {
    if (!(error instanceof HttpErrorResponse) || error.status !== 429) return;
    const value = error.headers.get('Retry-After');
    if (!value) return;
    const deadline = /^\d+$/.test(value) ? Date.now() + Number(value) * 1000 : Date.parse(value);
    if (!Number.isFinite(deadline) || deadline <= Date.now()) return;
    const tick = () => {
      this.retrySeconds.set(Math.max(0, Math.ceil((deadline - Date.now()) / 1000)));
      if (!this.retrySeconds()) clearInterval(this.timer);
    };
    clearInterval(this.timer);
    tick();
    this.timer = setInterval(tick, 1000);
  }

  async submit() {
    if (this.busy() || this.retrySeconds()) return;
    this.form.markAllAsTouched();
    if (this.form.invalid) return;
    this.busy.set(true);
    this.error.set('');
    const { email, password } = this.form.getRawValue();
    try {
      await this.auth.login(email, password);
      this.form.controls.password.reset();
      await this.router.navigateByUrl(this.auth.home, { replaceUrl: true });
    } catch (error) {
      this.error.set(errorMessage(error));
      this.respectLimit(error);
    } finally {
      this.busy.set(false);
    }
  }
}
