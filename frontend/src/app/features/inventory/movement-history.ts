import { EmptyState } from '../../shared/components/feedback/feedback';
import { Skeleton } from '../../shared/components/feedback/feedback';
import { DatePipe } from '@angular/common';
import { Component, computed, effect, inject, input, signal } from '@angular/core';
import { errorMessage } from '../../core/http/api';
import { InventoryApi } from './inventory-api';
import { Movement, movementLabel } from './inventory.models';

@Component({
  selector: 'app-movement-history',
  imports: [EmptyState, Skeleton, DatePipe],
  templateUrl: './movement-history.html',
  styleUrl: './inventory.css',
})
export class MovementHistory {
  readonly inventoryId = input.required<number>();
  readonly revision = input(0);
  private readonly api = inject(InventoryApi);
  readonly label = movementLabel;
  readonly pageSize = 20;
  readonly page = signal(0);
  readonly retry = signal(0);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly rows = signal<Movement[]>([]);
  readonly visible = computed(() => this.rows().slice(0, this.pageSize));

  constructor() {
    effect((onCleanup) => {
      const id = this.inventoryId();
      const page = this.page();
      this.revision();
      this.retry();
      let active = true;
      onCleanup(() => {
        active = false;
      });
      this.loading.set(true);
      this.error.set('');
      // The API's total counts only the batch returned. One extra row indicates another page.
      this.api
        .history(id, this.pageSize + 1, page * this.pageSize)
        .then((result) => {
          if (active) this.rows.set(result.movimientos);
        })
        .catch((error) => {
          if (active) this.error.set(errorMessage(error));
        })
        .finally(() => {
          if (active) this.loading.set(false);
        });
    });
  }
}
