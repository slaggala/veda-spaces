# Deployment: Veda Spaces

How changes reach `https://www.vedaspaces.com`, how to check them, and how to undo them. For one-time Cloudflare setup, see [cloudflare-pages.md](cloudflare-pages.md).

---

## Deployment workflow

Nothing is compiled. Cloudflare Pages publishes `dist/` exactly as committed.

```
edit dist/ → preview locally → push branch → check preview URL → merge to main → production
```

1. **Branch**
   ```sh
   git switch -c update/<short-description>
   ```
2. **Edit** files in `dist/`.
3. **Preview locally**
   ```sh
   python3 -m http.server 4173 -d dist
   ```
   Open `http://127.0.0.1:4173/` and check it at desktop width and at phone width (browser dev tools → 390 px).
4. **Push the branch**
   ```sh
   git add -A && git commit -m "Describe the change" && git push -u origin HEAD
   ```
   Cloudflare builds a preview at `https://<branch>.veda-spaces.pages.dev` (the link also appears on the GitHub commit or PR).
5. **Check the preview** on a real phone. `_headers` and `404.html` only take effect on Cloudflare, so this is the first place to confirm them.
6. **Merge to `main`** (PR merge or `git switch main && git merge --ff-only <branch> && git push`). Production deploys in under a minute.
7. Run **Post-deployment validation** below.

---

## Release checklist

Before merging to `main`:

- [ ] Every `src`/`href` into `assets/` matches an existing file, with exact case (Pages paths are case-sensitive)
- [ ] `404.html` uses root-absolute paths only (`/assets/...`, `/favicon.svg`)
- [ ] No `localhost`, `127.0.0.1` or `http://` URLs:
      `grep -rnE 'localhost|127\.0\.0\.1|http://' dist --include='*.html' --include='*.js' --include='*.css'`
- [ ] Phone/WhatsApp number identical in `index.html`, `404.html` and `assets/app.js`
- [ ] Email identical in `index.html` and `404.html`
- [ ] If the headline or description changed, `<title>`, `description`, `og:*` and `twitter:*` in `index.html` are updated together
- [ ] If `share-image.jpg` changed, it's still exactly 1200×630 and under 300 KB
- [ ] New images are compressed (JPG q≈80, or AVIF) and under 500 KB
- [ ] New pages are added to `sitemap.xml`
- [ ] Footer year current in `index.html` and `404.html`
- [ ] No `.DS_Store` or other stray files committed (`git status`)
- [ ] Preview URL checked on a phone

---

## Rollback procedure

A rollback is instant and doesn't rebuild anything.

1. Cloudflare dashboard → **Workers & Pages → veda-spaces → Deployments**.
2. Find the last good **Production** deployment (the one before the bad commit).
3. **⋯ → Rollback to this deployment** → confirm.
4. Hard-refresh `https://www.vedaspaces.com` to confirm.
5. Fix the code: `git revert <bad-sha> && git push`. Otherwise the next push to `main` redeploys the broken change.

Rollback only changes the site. It doesn't touch DNS, redirect rules or SSL settings, so if one of those caused the problem, undo it separately.

---

## Domain verification checklist

Run at launch and after any DNS or Cloudflare rule change.

- [ ] `dig +short NS vedaspaces.com` → `kaiser.ns.cloudflare.com`, `romina.ns.cloudflare.com`
- [ ] Pages → Custom domains: `www.vedaspaces.com` **Active**, `vedaspaces.com` **Active**
- [ ] DNS → Records: `www` and `@` are CNAMEs to `veda-spaces.pages.dev`, **Proxied** (orange cloud)
- [ ] MX (5 Google hosts), SPF TXT and `google-site-verification` TXT unchanged
- [ ] Redirect Rule `Apex to www` enabled
- [ ] SSL/TLS mode **Full (strict)**, **Always Use HTTPS** on

---

## Post-deployment validation

### 1. Status codes and redirects

```sh
curl -sI https://www.vedaspaces.com/            | head -1   # HTTP/2 200
curl -sI https://vedaspaces.com/                | grep -iE '^(HTTP|location)'   # 301 → https://www.vedaspaces.com/
curl -sI http://www.vedaspaces.com/             | grep -iE '^(HTTP|location)'   # 301 → https://
curl -sI "https://vedaspaces.com/?utm=test"     | grep -i location              # query string preserved
curl -sI https://www.vedaspaces.com/nope        | head -1   # HTTP/2 404  (not 200)
curl -sI https://www.vedaspaces.com/robots.txt  | head -1   # 200
curl -sI https://www.vedaspaces.com/sitemap.xml | head -1   # 200
curl -sI https://www.vedaspaces.com/assets/share-image.jpg | grep -iE '^(HTTP|content-type)'   # 200, image/jpeg
curl -sI https://www.vedaspaces.com/apple-touch-icon.png | head -1   # 200
curl -sI https://www.vedaspaces.com/ | grep -iE 'x-content-type-options|referrer-policy|x-frame-options'   # _headers applied
```

### 2. Browser

- [ ] Home page loads with fonts, hero image and logo; the browser console shows no 404s
- [ ] Every nav link scrolls to its section; the mobile menu opens and closes
- [ ] Portfolio images open the viewer; Esc and × close it
- [ ] The enquiry form opens WhatsApp with the details pre-filled, to +91 95151 25153
- [ ] `tel:`, WhatsApp, email and Instagram links work on a phone
- [ ] `https://www.vedaspaces.com/anything` shows the branded 404 page, and its Home button works
- [ ] Favicon shows in the browser tab
- [ ] iPhone Safari → Share → Add to Home Screen shows the Veda Spaces icon

### 3. Social previews

- [ ] Facebook Sharing Debugger (`developers.facebook.com/tools/debug`) → enter the URL → **Scrape Again** → image, title and description appear
- [ ] LinkedIn Post Inspector (`linkedin.com/post-inspector`) → same
- [ ] Send `https://www.vedaspaces.com` in a WhatsApp chat → the preview card shows the share image

WhatsApp and Facebook cache previews. If the card is stale after a change, re-scrape in the Facebook debugger, and for WhatsApp test with `https://www.vedaspaces.com/?v=2`.

### 4. Search and performance

- [ ] Google Search Console: add the **Domain** property `vedaspaces.com` (verify through the existing TXT record, or add the one Search Console gives), then submit `https://www.vedaspaces.com/sitemap.xml`
- [ ] PageSpeed Insights (`pagespeed.web.dev`) on the home page, mobile: note the scores as the baseline
- [ ] Chrome DevTools → Lighthouse → SEO: 100 expected

---

## Share image

`dist/assets/share-image.jpg` is referenced as `https://www.vedaspaces.com/assets/share-image.jpg` by `og:image` and `twitter:image`.

| Spec | Value |
|---|---|
| Size | **1200 × 630 px** (1.91:1). Facebook, LinkedIn, WhatsApp and X all use this ratio. |
| Format | JPEG, sRGB, progressive, quality ~85, **under 300 KB** (WhatsApp may skip images over ~600 KB) |
| Safe zone | Keep logo and text inside the **centred 630 × 630 square**. WhatsApp and some LinkedIn layouts crop to a square thumbnail. |
| Background | Real Veda Spaces interior photography, darkened about 25% so the brand panel stands out |
| Brand panel | Centred cream card `#fbf7ef`, with a 1 px copper `#ad6d54` inner rule inset 14 px |
| Logo | `veda-logo.png` full lockup (mark + wordmark + "Design with sense. Built with care."), dark ink `#281a13`, at native resolution (not upscaled) |
| Supporting text | "RESIDENTIAL INTERIORS · HYDERABAD" in a sans typeface (Manrope/Avenir), copper, tracked +3 px; `www.vedaspaces.com` in a serif typeface (Cormorant/Didot), ink |
| Avoid | Text under about 14 px (unreadable in a WhatsApp thumbnail), anything important within 60 px of the edges, transparent PNGs (some apps show them on black) |

**Current file:** generated from `assets/home.avif` (a 2000 px-wide source crop, downscaled so it stays sharp) with the brand card composited in the centre. Instagram doesn't render link previews in feed posts; this image is used when the link is shared in Instagram DMs, and for the link-in-bio preview.

To replace it with a designed version, export at exactly 1200×630 to the same path and filename, then re-scrape in the Facebook debugger.
