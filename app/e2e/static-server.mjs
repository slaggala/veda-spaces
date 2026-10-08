// Static server for the marketing site that applies dist/_headers the way Cloudflare Pages does, so browser
// tests run under the production Content-Security-Policy (IR-32).
//   node e2e/static-server.mjs <root> <port> [api-origin]
// With [api-origin], connect-src's production API origin is swapped for it and <meta name="veda-api-base">
// and the Turnstile site key are filled in, turning intake on for the test (flag-on mode).
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';

const [root, port, apiOrigin] = process.argv.slice(2);
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.avif': 'image/avif', '.ico': 'image/x-icon', '.xml': 'application/xml',
  '.txt': 'text/plain' };

function parseHeaders(text) {
  const rules = [];
  let current = null;
  for (const line of text.split('\n')) {
    if (!line.trim() || line.trim().startsWith('#')) continue;
    if (!line.startsWith(' ')) { current = { pattern: line.trim(), headers: {} }; rules.push(current); continue; }
    const [name, ...rest] = line.trim().split(':');
    current.headers[name.trim()] = rest.join(':').trim();
  }
  return rules;
}
const rules = parseHeaders(fs.readFileSync(path.join(root, '_headers'), 'utf8'));
const matches = (pattern, url) => (pattern.endsWith('*') ? url.startsWith(pattern.slice(0, -1)) : url === pattern);

http.createServer((req, res) => {
  const url = new URL(req.url, 'http://x').pathname;
  let file = path.join(root, url === '/' ? 'index.html' : url);
  if (!path.extname(file) && fs.existsSync(`${file}.html`)) file = `${file}.html`; // Pages serves /estimate as estimate.html
  if (!file.startsWith(path.resolve(root)) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
    file = path.join(root, '404.html');
    res.statusCode = 404;
  }
  for (const rule of rules) {
    if (!matches(rule.pattern, url)) continue;
    for (const [k, v] of Object.entries(rule.headers)) {
      res.setHeader(k, apiOrigin && k === 'Content-Security-Policy'
        ? v.replace('https://api.vedaspaces.com', apiOrigin).replace(' upgrade-insecure-requests', '') : v);
    }
  }
  if (!apiOrigin && res.getHeader('Content-Security-Policy')) {
    res.setHeader('Content-Security-Policy', String(res.getHeader('Content-Security-Policy')).replace(' upgrade-insecure-requests', ''));
  }
  let body = fs.readFileSync(file);
  if (apiOrigin && (file.endsWith('index.html') || file.endsWith('estimate.html'))) {
    body = Buffer.from(body.toString()
      .replace('<meta name="veda-api-base" content="">', `<meta name="veda-api-base" content="${apiOrigin}">`)
      .replace('<meta name="veda-turnstile-sitekey" content="">', '<meta name="veda-turnstile-sitekey" content="1x00000000000000000000AA">')
      .replace('<meta name="veda-estimator" content="">', '<meta name="veda-estimator" content="on">'));
  }
  res.setHeader('Content-Type', TYPES[path.extname(file)] || 'application/octet-stream');
  res.end(body);
}).listen(Number(port), () => console.log(`serving ${root} on ${port}${apiOrigin ? ` (intake on → ${apiOrigin})` : ''}`));
