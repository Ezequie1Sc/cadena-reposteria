import { WelcomeBanner } from '../../features/administration/welcome';
import { Component, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthService } from '../../core/auth/auth';
import { EMPLOYEE_NAV } from '../../core/config/navigation';
import { NavIcon } from '../../shared/components/icon/icon';

@Component({
  selector: 'app-employee-layout',
  imports: [WelcomeBanner, RouterLink, RouterLinkActive, RouterOutlet, NavIcon],
  templateUrl: './employee-layout.html',
  styleUrl: './employee-layout.css',
})
export class EmployeeLayout {
  readonly auth = inject(AuthService);
  readonly nav = EMPLOYEE_NAV;
}
