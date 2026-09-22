# Run — DrRoshan static site

Static multi-page site (no package.json, no dependencies): `index.html`, `cart.html`, `checkout.html`, `payment.html`, `admin.html` (order-management panel reading `localStorage.hr_orders`), `profile.html` (purchased courses + progress from `hr_orders` / `hr_course_progress`), shared `shop.css` / `shop.js`, `profile.jpg`, plus PWA files (`manifest.json`, `sw.js`, `pwa-*.png`, `favicon-*.png`, `apple-touch-icon.png`).

## How to reproduce the icon artifacts

All icons are generated from `profile.jpg` (which is actually a JPEG — System.Drawing decodes it fine):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .freebuff/make-favicons.ps1
```

Regenerates the circular favicons (16/32/64/180), the PWA icons `pwa-192.png` / `pwa-512.png`, and the maskable variants `pwa-maskable-192.png` / `pwa-maskable-512.png` (photo at 76% on the `#0f172a` brand background).

## How to run the server

Any static file server rooted at the project root works. The bundled zero-dependency one:

```powershell
powershell -NoProfile -Command "(Start-Process -FilePath 'node.exe' -ArgumentList '.freebuff/preview-server.js','8877' -RedirectStandardOutput '.freebuff/preview-68ac946c-61ed-41b5-ac00-ec7df657dd40.log' -RedirectStandardError '.freebuff/preview-68ac946c-61ed-41b5-ac00-ec7df657dd40.log.err' -WindowStyle Hidden -PassThru).Id"
```

- Server script: `.freebuff/preview-server.js` (Node built-ins only, serves all HTML/CSS/JS/PNG with no-cache).
- Port: 8877 (free default chosen for this project; pass another port as the second argument if taken).
- Verify: `curl http://localhost:8877/index.html` should return 200 (also check `/cart.html`, `/checkout.html`, `/payment.html`).
- Then register the preview with URL `http://localhost:8877/index.html` and the printed pid.

Notes:
- A multi-file server (not single-file htmlPath preview) is required because the shop flow navigates across pages and shares state via `localStorage` / `sessionStorage` per origin.
- `Start-Process` may not print/return promptly through the shell wrapper — confirm the pid with `Get-Process -Id <pid>` and the URL with curl instead of trusting the command exit.
