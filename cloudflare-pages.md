# Cloudflare Pages: setup reference

One-time configuration that puts `dist/` live at `https://www.vedaspaces.com`, with `https://vedaspaces.com` redirecting to it with a 301.

**Canonical host: `www.vedaspaces.com`.** The canonical link, `og:url`, `robots.txt`, `sitemap.xml` and the footer all use it. Don't publish the apex as a separate copy of the site.

---

## 1. Pages project settings

**Workers & Pages → Create → Pages → Connect to Git** → select the GitHub repository.

| Setting | Value | Why |
|---|---|---|
| Project name | `veda-spaces` | Gives `veda-spaces.pages.dev` (any free name works) |
| Production branch | `main` | |
| Framework preset | **None** | No framework |
| Build command | **`exit 0`** | Nothing to build. `exit 0` succeeds immediately and satisfies the UI if it insists on a value. Leaving it empty also works. |
| Build output directory | **`dist`** | The folder that gets published |
| Root directory (advanced) | **`/`** (or empty) | Repository root |
| Environment variables | none | |
| Build system version | default (latest) | Not relevant because nothing is built |

After **Save and Deploy**, the first build should finish in under a minute. Open `https://veda-spaces.pages.dev` and confirm the site renders before attaching domains.

**Settings → Builds & deployments → Preview branches:** leave it on *All non-production branches*.

### Files Pages reads from `dist/`

| File | Effect |
|---|---|
| `404.html` | Served with HTTP **404** for unknown paths. Without it, Pages serves `index.html` with a 200 for every URL (SPA mode). |
| `_headers` | Adds security headers to every response and sets a 1-day browser cache on `/assets/*` |

Asset filenames aren't content-hashed, so `_headers` deliberately avoids `immutable` and year-long cache lifetimes. Otherwise a replaced image could stay stale in visitors' browsers.

---

## 2. DNS: state before setup

As of 2026-09-28:

| Record | Value | Action |
|---|---|---|
| NS | `kaiser.ns.cloudflare.com`, `romina.ns.cloudflare.com` | ✅ Zone is on Cloudflare, so nothing needs to change at the registrar |
| `vedaspaces.com` A/AAAA/CNAME | *none* | Pages creates it (step 3) |
| `www` CNAME | *none* | Pages creates it (step 3) |
| MX `aspmx.l.google.com` + alt1–4 | Google Workspace | ⛔ **Do not touch** |
| TXT `v=spf1 include:_spf.google.com ~all` | SPF | ⛔ **Do not touch** |
| TXT `google-site-verification=…` | Google | ⛔ **Do not touch** |

If an old Amplify `CNAME` for `www` or `@`, or an `_<hash>` validation CNAME from Amplify, has appeared since then, **delete it before step 3** so the hostname points only at Pages.

Check from a terminal:

```sh
dig +short NS vedaspaces.com
dig +short vedaspaces.com
dig +short www.vedaspaces.com
dig +short MX vedaspaces.com
```

---

## 3. Custom domains

In the Pages project, go to **Custom domains → Set up a custom domain**.

1. Enter `www.vedaspaces.com` → **Continue** → **Activate domain**.
   Cloudflare creates a **proxied** `CNAME www → veda-spaces.pages.dev`.
2. Repeat for `vedaspaces.com`.
   Cloudflare creates a **proxied**, flattened `CNAME @ → veda-spaces.pages.dev`.

Both show **Initializing**, then **Active**, usually within 5 minutes and occasionally up to 24 hours. The apex is attached so that it gets an edge certificate and never returns an error before the redirect runs.

> Don't create these CNAMEs by hand in the DNS tab. A hand-made CNAME that isn't registered as a Pages custom domain returns **522** errors.

---

## 4. Apex → www redirect

Pages `_redirects` handles paths, not hostnames, so use a zone-level Redirect Rule.

**vedaspaces.com zone → Rules → Redirect Rules → Create rule** (or pick the template *"Redirect from Root to WWW"*):

| Field | Value |
|---|---|
| Rule name | `Apex to www` |
| If incoming requests match | Custom filter expression: **Hostname** *equals* `vedaspaces.com` |
| Then | **Dynamic** redirect |
| Expression | `concat("https://www.vedaspaces.com", http.request.uri.path)` |
| Status code | **301** |
| Preserve query string | ✅ |

Deploy the rule. It runs at the edge before Pages, so apex requests never reach the site.

**Optional: redirect `veda-spaces.pages.dev` as well.** Zone Redirect Rules don't apply to `pages.dev`, so use **Account → Bulk Redirects**. Create a list with one entry, source `veda-spaces.pages.dev` → target `https://www.vedaspaces.com`, status 301, *preserve query string* and *subpath matching* **on**, *include subdomains* **off**. Then create a Bulk Redirect rule that uses the list. Keep *include subdomains* off, or branch previews on `<branch>.veda-spaces.pages.dev` would redirect too. The canonical tag already points search engines at `www`, so this step is optional.

---

## 5. SSL / TLS

**vedaspaces.com zone → SSL/TLS**:

| Setting | Value |
|---|---|
| Encryption mode | **Full (strict)**. Pages presents a valid certificate, so strict is safe. |
| Edge Certificates → Always Use HTTPS | **On** |
| Edge Certificates → Automatic HTTPS Rewrites | On |
| Edge Certificates → Minimum TLS Version | 1.2 |
| Edge Certificates → HSTS | **Off at launch.** Turn it on after about a week of clean operation (max-age 6 months, include subdomains only if every subdomain serves HTTPS). |

Verify:

```sh
# Certificate covers both hostnames, issued by a public CA
echo | openssl s_client -connect www.vedaspaces.com:443 -servername www.vedaspaces.com 2>/dev/null | openssl x509 -noout -subject -issuer -dates -ext subjectAltName
echo | openssl s_client -connect vedaspaces.com:443 -servername vedaspaces.com 2>/dev/null | openssl x509 -noout -subject -issuer -dates -ext subjectAltName

# HTTP upgrades to HTTPS
curl -sI http://www.vedaspaces.com | grep -iE '^(HTTP|location)'
```

Expected: `notAfter` in the future, SAN includes the hostname, and HTTP returns `301` to `https://`.

---

## 6. DNS validation (after setup)

```sh
dig +short www.vedaspaces.com      # Cloudflare anycast IPs (104.x / 172.x), not a pages.dev name — the record is proxied
dig +short vedaspaces.com          # Cloudflare anycast IPs
dig +short MX vedaspaces.com       # still the five Google MX hosts
dig +short TXT vedaspaces.com      # SPF + google-site-verification still present
```

In the dashboard, both hostnames should show **Active** under **Pages → Custom domains**, and **DNS → Records** should show both CNAMEs with an orange cloud (Proxied).

---

## Limits

| Limit | Pages | This site |
|---|---|---|
| Files per deployment | 20,000 | ~27 |
| Max file size | 25 MiB | largest is `wardrobe.avif`, 733 KB |
| Builds per month (free plan) | 500 | one per push |
