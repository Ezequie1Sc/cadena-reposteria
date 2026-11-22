import { NgTemplateOutlet } from '@angular/common';
import { Component, computed, ElementRef, inject, viewChild } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter, map } from 'rxjs';
import { AuthService } from '../../core/auth/auth';
import { ADMIN_GROUPS, ADMIN_NAV } from '../../core/config/navigation';
import { NavIcon } from '../../shared/components/icon/icon';

@Component({
  selector: 'app-admin-layout',
  imports: [NgTemplateOutlet, RouterLink, RouterLinkActive, RouterOutlet, NavIcon],
  templateUrl: './admin-layout.html',
  styleUrl: './admin-layout.css',
})
export class AdminLayout {
  readonly auth = inject(AuthService);
  readonly groups = ADMIN_GROUPS;
  private readonly router = inject(Router);
  private readonly drawer = viewChild.required<ElementRef<HTMLDialogElement>>('drawer');
  private readonly url = toSignal(
    this.router.events.pipe(
      filter((event) => event instanceof NavigationEnd),
      map((event) => event.urlAfterRedirects),
    ),
    { initialValue: this.router.url },
  );
  readonly section = computed(() => {
    const segment = this.url().split(/[/?#]/)[2];
    return ADMIN_NAV.find((item) => item.path === segment)?.label ?? 'Resumen';
  });

  openMenu(): void {
    this.drawer().nativeElement.showModal();
  }
  closeMenu(): void {
    this.drawer().nativeElement.close();
  }
}
