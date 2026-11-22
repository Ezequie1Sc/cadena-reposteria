/** Prints only inert text and the small set of elements used by FastAPI's ticket template. */
export async function printTicketHtml(html: string): Promise<void> {
  const source = new DOMParser().parseFromString(html, 'text/html');
  if (!source.querySelector('h1') || !source.querySelector('table')) {
    throw new Error('La respuesta del servidor no contiene un ticket imprimible.');
  }
  const frame = document.createElement('iframe');
  frame.setAttribute('aria-label', 'Ticket para impresión');
  frame.setAttribute('sandbox', 'allow-same-origin allow-modals');
  frame.style.cssText = 'position:fixed;left:-150vw;width:800px;height:800px;border:0';
  document.body.append(frame);
  try {
    const target = frame.contentDocument;
    const view = frame.contentWindow;
    if (!target || !view) throw new Error('El navegador impidió abrir la impresión.');
    target.documentElement.lang = 'es';
    target.title = source.title;
    const style = target.createElement('style');
    style.textContent =
      'body{font:15px sans-serif;max-width:760px;margin:auto}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:8px;border-bottom:1px solid #bbb}h1{font-size:20px;overflow-wrap:anywhere}';
    target.head.append(style);
    const allowed = new Set([
      'H1',
      'H2',
      'P',
      'TABLE',
      'THEAD',
      'TBODY',
      'TR',
      'TD',
      'TH',
      'UL',
      'LI',
      'STRONG',
      'BR',
    ]);
    function appendSafe(from: Node, to: Node): void {
      for (const node of Array.from(from.childNodes)) {
        if (node.nodeType === Node.TEXT_NODE)
          to.appendChild(target!.createTextNode(node.textContent ?? ''));
        else if (node instanceof Element && allowed.has(node.tagName)) {
          const next = target!.createElement(node.tagName.toLowerCase());
          to.appendChild(next);
          appendSafe(node, next);
        }
      }
    }
    appendSafe(source.body, target.body);
    await new Promise<void>((resolve) =>
      requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
    );
    const cleanup = () => frame.remove();
    view.addEventListener('afterprint', cleanup, { once: true });
    view.focus();
    view.print();
    window.setTimeout(cleanup, 120000);
  } catch (error) {
    frame.remove();
    throw error;
  }
}
