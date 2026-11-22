import { NavIcon } from '../../../../shared/components/icon/icon';
import { Component, computed, input, output, signal } from '@angular/core';
import { Category, Product, cents, currency } from '../models/pos';

@Component({
  imports: [NavIcon],
  selector: 'app-pos-catalog',
  templateUrl: './pos-catalog.html',
  styleUrl: './pos-catalog.css',
})
export class PosCatalog {
  readonly products = input.required<Product[]>();
  readonly categories = input.required<Category[]>();
  readonly stock = input.required<Map<number, number>>();
  readonly locked = input(false);
  readonly add = output<Product>();
  readonly query = signal('');
  readonly filter = signal<number | null>(null);
  readonly broken = signal<Set<string>>(new Set());
  readonly shown = computed(() => {
    const term = this.normalize(this.query().trim());
    return this.products().filter(
      (p) =>
        p.activo &&
        (!this.filter() || this.filter() === p.categoria_id) &&
        this.normalize(p.nombre + ' ' + p.sku).includes(term),
    );
  });
  readonly price = (value: string) => currency(cents(value));
  private normalize(text: string) {
    return text
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase();
  }
  imageFailed(url: string) {
    this.broken.update((set) => new Set([...set, url]));
  }
}
