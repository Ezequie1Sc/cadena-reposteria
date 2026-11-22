import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { ToastComponent } from './shared/components/toast/toast';
import { ConfirmDialog } from './shared/components/confirm-dialog/confirm-dialog';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, ToastComponent, ConfirmDialog],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {}
