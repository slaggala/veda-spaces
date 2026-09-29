# Veda Spaces website

Source repository for [www.vedaspaces.com](https://www.vedaspaces.com), the Veda Spaces residential interior design website.

The site is plain HTML, CSS and JavaScript, with no framework, package manager, build step or server process. The `dist/` folder **is** the website and is published to Cloudflare Pages exactly as committed.

## Project structure

```
dist/
├── index.html            page content and structure (single page, #anchor sections)
├── 404.html              branded not-found page (served with HTTP 404)
├── _headers              Cloudflare Pages response headers
├── robots.txt            crawler rules + sitemap location
├── sitemap.xml
├── favicon.svg           modern browsers
├── favicon.ico           legacy browsers / crawlers requesting /favicon.ico
├── apple-touch-icon.png  iOS home-screen icon (180×180)
└── assets/
    ├── styles.css        core layout and responsive styles
    ├── enhancements.css  brand theme and visual refinements
    ├── app.js            navigation, portfolio viewer, WhatsApp enquiry form, motion
    ├── share-image.jpg   social preview (Open Graph / Twitter), 1200×630
    └── *.jpg, *.avif, veda-logo.png
deployment.md             release workflow, checklists, rollback, validation
cloudflare-pages.md       Pages project, domains, redirect, SSL, DNS
```

## Preview locally

From the repository root:

```sh
python3 -m http.server 4173 -d dist
```

Open `http://127.0.0.1:4173/`. On Windows, use `python` instead of `python3`.

The local server doesn't apply `_headers` and doesn't serve `404.html` for missing pages. Use a Cloudflare preview deployment to check those.

## Deploy with Cloudflare Pages

The site deploys automatically from GitHub:

- A push to **`main`** deploys to production at `https://www.vedaspaces.com`.
- A push to **any other branch** creates a preview at `https://<branch>.<project>.pages.dev`.

| Pages setting | Value |
|---|---|
| Framework preset | None |
| Build command | `exit 0` |
| Build output directory | `dist` |
| Root directory | `/` |

- **[deployment.md](deployment.md)**: day-to-day workflow, release checklist, rollback, post-deployment validation
- **[cloudflare-pages.md](cloudflare-pages.md)**: one-time project setup, custom domains, apex → www redirect, SSL, DNS

## Contact details

The enquiry form opens WhatsApp with the visitor's project details pre-filled. If the phone number changes, update it in:

- `dist/assets/app.js` (form destination)
- `dist/index.html` (`tel:` link and two `wa.me` links)
- `dist/404.html` (`tel:` link and `wa.me` link)

Don't change the MX, SPF or Google verification DNS records. They carry mail for `interiors@vedaspaces.com`.

## Veda Spaces platform (P0)

- `api/` — Flask API, SQLAlchemy, Alembic (see `api/README.md`)
- `app/` — Veda Workspace staff app, Lit + TypeScript (see `app/README.md`)
- `docs/architecture/` — certified architecture; `docs/implementation/P0-implementation-report.md` — implementation report

The website enquiry form posts to the API only when `<meta name="veda-api-base">` in `dist/index.html` is set;
otherwise it keeps the WhatsApp hand-off.
