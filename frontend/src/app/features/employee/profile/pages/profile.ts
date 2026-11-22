import { Component, inject } from '@angular/core';
import { AuthService } from '../../../../core/auth/auth';

@Component({
  selector: 'app-employee-profile',
  templateUrl: './profile.html',
  styleUrl: './profile.css',
})
export class ProfilePage {
  readonly auth = inject(AuthService);
}
