// Serve the production bundle with SPA fallback. Binds only to loopback.
import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { resolve, extname, sep } from 'node:path';
export async function frontendServer() {
  const root = resolve('dist/dulcegestion-web/browser');
  const server = createServer(async (req, res) => {
    try {
      const url = new URL(req.url, 'http://localhost');
      if (url.pathname.startsWith('/api/')) {
        if (!process.env.DG_TEST_API) {
          res.writeHead(501).end();
          return;
        }
        const base = new URL(process.env.DG_TEST_API);
        if (base.hostname !== '127.0.0.1')
          throw Error('Only a disposable local test server is supported');
        const chunks = [];
        for await (const c of req) chunks.push(c);
        const response = await fetch(base.origin + url.pathname.slice(4) + url.search, {
          method: req.method,
          headers: {
            'content-type': req.headers['content-type'] ?? 'application/json',
            ...(req.headers['idempotency-key']
              ? { 'Idempotency-Key': req.headers['idempotency-key'] }
              : {}),
            ...(req.headers.authorization ? { authorization: req.headers.authorization } : {}),
          },
          body: chunks.length ? Buffer.concat(chunks) : undefined,
        });
        res
          .writeHead(response.status, {
            'content-type': response.headers.get('content-type') ?? 'application/json',
          })
          .end(Buffer.from(await response.arrayBuffer()));
        return;
      }
      let file = resolve(root, '.' + decodeURIComponent(url.pathname));
      if (file !== root && !file.startsWith(root + sep)) {
        res.writeHead(403).end();
        return;
      }
      if (
        !(await stat(file)
          .then((s) => s.isFile())
          .catch(() => false))
      )
        file = resolve(root, 'index.html');
      const mime = {
        '.html': 'text/html',
        '.js': 'text/javascript',
        '.css': 'text/css',
        '.json': 'application/json',
        '.svg': 'image/svg+xml',
        '.woff2': 'font/woff2',
        '.webp': 'image/webp',
      };
      res
        .writeHead(200, { 'Content-Type': mime[extname(file)] ?? 'application/octet-stream' })
        .end(await readFile(file));
    } catch {
      res.writeHead(500).end();
    }
  });
  await new Promise((ok) => server.listen(0, '127.0.0.1', ok));
  return {
    url: 'http://127.0.0.1:' + server.address().port,
    close: () => new Promise((ok) => server.close(ok)),
  };
}
