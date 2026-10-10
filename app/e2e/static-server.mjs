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
    if (line.trim().startsWith('! ')) { current.headers[line.trim().slice(2).trim()] = null; continue; } // Pages: detach
    const [name, ...rest] = line.trim().split(':');
    current.headers[name.trim()] = rest.join(':').trim();
  }
  return rules;
}
const rules = parseHeaders(fs.readFileSync(path.join(root, '_headers'), 'utf8'));
const matches = (pattern, url) => (pattern.endsWith('*') ? url.startsWith(pattern.slice(0, -1)) : url === pattern);

// The home sizes the page offers: the synthetic test card prices 2 and 3 BHK; a real card (session stack, real-card
// runs) prices only what staging offers, so those scripts pass SITE_HOME_SIZES=3BHK.
const HOME_SIZES = process.env.SITE_HOME_SIZES || '2BHK,3BHK';

http.createServer((req, res) => {
  const url = new URL(req.url, 'http://x').pathname;
  let file = path.join(root, url === '/' ? 'index.html' : url);
  if (!path.extname(file) && fs.existsSync(`${file}.html`)) file = `${file}.html`; // Pages serves /estimate as estimate.html
  if (fs.existsSync(file) && fs.statSync(file).isDirectory() && fs.existsSync(path.join(file, 'index.html'))) file = path.join(file, 'index.html'); // and /dir/ as dir/index.html
  if (!file.startsWith(path.resolve(root)) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
    file = path.join(root, '404.html');
    res.statusCode = 404;
  }
  for (const rule of rules) {
    if (!matches(rule.pattern, url)) continue;
    for (const [k, v] of Object.entries(rule.headers)) {
      if (v === null) { res.removeHeader(k); continue; }
      res.setHeader(k, apiOrigin && k === 'Content-Security-Policy'
        ? v.replace('https://api.vedaspaces.com', apiOrigin).replace(' upgrade-insecure-requests', '') : v);
    }
  }
  if (!apiOrigin && res.getHeader('Content-Security-Policy')) {
    res.setHeader('Content-Security-Policy', String(res.getHeader('Content-Security-Policy')).replace(' upgrade-insecure-requests', ''));
  }
  // V3 (ADR-013) shows catalog images served by the API. Only locally may its page load them: staging and production
  // keep the site-wide policy until the media host is decided.
  if (apiOrigin && file.endsWith('estimate-v3.html') && res.getHeader('Content-Security-Policy')) {
    res.setHeader('Content-Security-Policy', String(res.getHeader('Content-Security-Policy')).replace("img-src 'self' data:", `img-src 'self' data: ${apiOrigin}`));
  }
  let body = fs.readFileSync(file);
  if (apiOrigin && file.endsWith('estimate-v3.html')) {
    body = Buffer.from(body.toString()
      .replace('<meta name="veda-api-base" content="">', `<meta name="veda-api-base" content="${apiOrigin}">`)
      .replace('<meta name="veda-turnstile-sitekey" content="">', '<meta name="veda-turnstile-sitekey" content="1x00000000000000000000AA">')
      .replace('<meta name="veda-estimator-version" content="">', '<meta name="veda-estimator-version" content="v3">'));
  }
  if (apiOrigin && (file.endsWith('index.html') || file.endsWith('estimate.html'))) {
    body = Buffer.from(body.toString()
      .replace('<meta name="veda-api-base" content="">', `<meta name="veda-api-base" content="${apiOrigin}">`)
      .replace('<meta name="veda-turnstile-sitekey" content="">', '<meta name="veda-turnstile-sitekey" content="1x00000000000000000000AA">')
      .replace('<meta name="veda-estimator" content="">', '<meta name="veda-estimator" content="on">')
      .replace('<meta name="veda-estimator-home-sizes" content="">', `<meta name="veda-estimator-home-sizes" content="${HOME_SIZES}">`)
      .replace('<meta name="veda-estimator-property-types" content="">', '<meta name="veda-estimator-property-types" content="APARTMENT">')
      .replace('<meta name="veda-estimator-ux" content="">', `<meta name="veda-estimator-ux" content="${new URL(req.url, 'http://x').searchParams.get('ux') === 'v2' ? 'v2' : ''}">`));
  }
  res.setHeader('Content-Type', TYPES[path.extname(file)] || 'application/octet-stream');
  res.end(body);
}).listen(Number(port), () => console.log(`serving ${root} on ${port}${apiOrigin ? ` (intake on → ${apiOrigin})` : ''}`));
