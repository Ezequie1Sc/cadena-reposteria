import { Component, input } from '@angular/core';
import { NavIcon } from '../icon/icon';

@Component({
  selector: 'dg-skeleton',
  template: ` <div
    class="skeleton"
    [attr.data-shape]="shape()"
    role="status"
    aria-label="Cargando información"
    aria-busy="true"
  >
    @for (row of lines; track row) {
      <div aria-hidden="true"><i></i><i></i><i></i></div>
    }
  </div>`,
  styles: [
    `
      :host {
        display: block;
      }
      .skeleton {
        display: grid;
        gap: 12px;
        padding: 16px;
      }
      .skeleton div {
        display: flex;
        gap: 6%;
        align-items: center;
        min-height: 42px;
        border-bottom: 1px solid var(--border);
      }
      i {
        border-radius: 5px;
        height: 0.8rem;
        width: 30%;
        background: linear-gradient(100deg, #eee8e1 25%, #f8f5f1 44%, #eee8e1 65%);
        background-size: 220% 100%;
        animation: sweep 1.4s infinite;
      }
      i:first-child {
        width: 43%;
      }
      i:last-child {
        width: 14%;
      }
      [data-shape='cards'],
      [data-shape='dashboard'] {
        grid-template-columns: repeat(auto-fit, minmax(min(165px, 100%), 1fr));
      }
      [data-shape='cards'] div,
      [data-shape='dashboard'] div,
      [data-shape='detail'] div {
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 16px;
        flex-flow: column;
        align-items: start;
        justify-content: center;
        gap: 14px;
      }
      [data-shape='cards'] i:first-child {
        width: 100%;
        height: 88px;
      }
      [data-shape='dashboard'] div:last-child {
        grid-column: 1/-1;
        height: 145px;
      }
      [data-shape='detail'] {
        grid-template-columns: 1fr 1fr;
      }
      [data-shape='filter'] {
        width: 180px;
        padding: 0;
      }
      [data-shape='filter'] div:not(:first-child),
      [data-shape='chart'] div:not(:first-child) {
        display: none;
      }
      [data-shape='chart'] div {
        height: 175px;
        align-items: end;
      }
      [data-shape='chart'] i {
        height: 70%;
        width: 25%;
      }
      [data-shape='chart'] i:nth-child(2) {
        height: 95%;
      }
      @keyframes sweep {
        to {
          background-position: -220% 0;
        }
      }
      @media (prefers-reduced-motion: reduce) {
        i {
          animation: none;
        }
      }
    `,
  ],
})
export class Skeleton {
  readonly shape = input<'table' | 'cards' | 'dashboard' | 'detail' | 'filter' | 'chart'>('table');
  readonly lines = [0, 1, 2, 3];
}
@Component({
  selector: 'dg-empty',
  imports: [NavIcon],
  template: `<div class="blank">
    <dg-icon [name]="icon()" [size]="26" /><strong>{{ title() }}</strong>
    <p>{{ description() }}</p>
    <ng-content />
  </div>`,
  styles: [
    `
      .blank {
        display: grid;
        justify-items: center;
        text-align: center;
        padding: 32px 12px;
        gap: 7px;
      }
      .blank dg-icon {
        color: #835d44;
        background: #f5eae0;
        border-radius: 14px;
        padding: 12px;
      }
      .blank p {
        color: var(--muted);
        margin: 0;
        font-size: 0.88rem;
      }
    `,
  ],
})
export class EmptyState {
  readonly title = input.required<string>();
  readonly description = input.required<string>();
  readonly icon = input('search');
}
