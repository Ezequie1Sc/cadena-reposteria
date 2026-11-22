import { NavIcon } from '../icon/icon';
import { Component, ElementRef, effect, inject, viewChild } from '@angular/core';
import { DialogService } from '../../services/dialog';
import { AuthService } from '../../../core/auth/auth';

@Component({
  imports: [NavIcon],
  selector: 'app-confirm-dialog',
  template: `
    <dialog
      #modal
      aria-labelledby="confirm-title"
      aria-describedby="confirm-detail"
      (cancel)="onCancel($event)"
    >
      @if (service.current(); as item) {
        <div class="dialog-content">
          <div class="dialog-mark" aria-hidden="true">
            <dg-icon [name]="item.danger ? 'warning' : 'shield'" />
          </div>
          <h2 id="confirm-title">{{ item.title }}</h2>
          <p id="confirm-detail">{{ item.description }}</p>
          @if (service.error()) {
            <p role="alert" class="dialog-error">{{ service.error() }}</p>
          }
          <div class="dialog-actions">
            <button
              autofocus
              type="button"
              class="btn btn-secondary"
              [disabled]="service.busy()"
              (click)="service.cancel()"
            >
              Cancelar
            </button>
            <button
              type="button"
              class="btn"
              [class.btn-primary]="!item.danger"
              [class.btn-danger]="item.danger"
              [attr.aria-busy]="service.busy()"
              [disabled]="service.busy()"
              (click)="service.confirm()"
            >
              {{ service.busy() ? 'Procesando…' : item.confirmLabel }}
            </button>
          </div>
        </div>
      }
    </dialog>
  `,
  styles: [
    `
      dialog {
        border: 1px solid #ddd2c8;
        border-radius: 19px;
        color: #342d29;
        box-shadow: 0 22px 80px #382c2638;
        background: #fffdfb;
        padding: 0;
        margin: auto;
        width: min(455px, calc(100vw - 32px));
        max-height: 90dvh;
      }
      dialog::backdrop {
        background: #251b179c;
      }
      .dialog-content {
        padding: 28px;
      }
      .dialog-mark {
        display: grid;
        place-items: center;
        background: #f4e6d9;
        border-radius: 12px;
        width: 40px;
        height: 40px;
        font-size: 1.4rem;
        font-weight: 700;
        color: #81533b;
      }
      h2 {
        font-size: 1.4rem;
        letter-spacing: -0.04em;
        margin: 17px 0 6px;
      }
      p {
        color: #675b53;
        white-space: pre-line;
        line-height: 1.55;
      }
      .dialog-actions {
        display: flex;
        justify-content: flex-end;
        gap: 10px;
        margin-top: 22px;
      }
      .dialog-error {
        color: #9b332b;
        background: #fff0ee;
        padding: 10px;
        border-radius: 8px;
      }
    `,
  ],
})
export class ConfirmDialog {
  readonly service = inject(DialogService);
  private readonly auth = inject(AuthService);
  private readonly modal = viewChild<ElementRef<HTMLDialogElement>>('modal');

  constructor() {
    effect(() => {
      const dialog = this.modal()?.nativeElement;
      if (!dialog) return;
      if (this.service.current() && this.auth.user()) {
        if (!dialog.open) dialog.showModal();
      } else {
        if (dialog.open) dialog.close();
        if (!this.auth.user() && this.service.current()) this.service.reset();
      }
    });
  }

  onCancel(event: Event) {
    event.preventDefault();
    this.service.cancel();
  }
}
