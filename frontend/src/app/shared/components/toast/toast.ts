import { Component, inject } from '@angular/core';
import { ToastService } from '../../services/toast.service';
import { NavIcon } from '../icon/icon';

@Component({
  selector: 'app-toast',
  imports: [NavIcon],
  templateUrl: './toast.html',
  styleUrl: './toast.css',
})
export class ToastComponent {
  readonly toast = inject(ToastService);
}
