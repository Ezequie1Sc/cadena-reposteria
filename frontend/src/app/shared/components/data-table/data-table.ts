import { Component, input } from '@angular/core';

@Component({
  selector: 'dg-data-table',
  template: `
    <div
      class="table-wrap overflow-x-auto"
      tabindex="0"
      role="region"
      [attr.aria-label]="caption()"
    >
      <table class="w-full text-left">
        <caption class="sr-only">
          {{
            caption()
          }}
        </caption>
        <thead>
          <tr>
            @for (column of headers(); track $index) {
              <th scope="col">{{ column }}</th>
            }
          </tr>
        </thead>
        <tbody>
          @for (row of rows(); track $index) {
            <tr>
              @for (cell of row; track $index) {
                <td>{{ cell }}</td>
              }
            </tr>
          }
        </tbody>
      </table>
    </div>
  `,
})
export class DataTable {
  readonly caption = input.required<string>();
  readonly headers = input.required<readonly string[]>();
  readonly rows = input.required<readonly (readonly string[])[]>();
}
