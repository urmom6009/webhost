# HH88TRANCE

Docker Compose-ready React site plus the Telegram storefront backend for the HH88TRANCE adult audio/video brand.

The public site now uses a refined dark catalog system: hard-edged frames, steel grid rails, red status accents, condensed uppercase headings, and live video availability pulled from the backend product catalog. Public copy remains sanitized for hosting and payment-provider risk.

## Tech Stack

- Vite
- React
- TypeScript
- Vitest and Testing Library
- ESLint
- Docker Compose main runtime with Nginx, FastAPI, Postgres, Prometheus, and Grafana
- FastAPI Telegram/Stripe storefront backend under `backend/`
- Pytest and Alembic for backend validation and migrations

## Commands

- `npm install` installs dependencies.
- `npm run dev` starts the local Vite server.
- `npm test` runs the focused unit and interaction tests.
- `npm run lint` runs ESLint.
- `npm run build` type-checks and builds the production bundle.
- `npm run preview` serves the production build locally.
- `python -m venv .venv && .venv/bin/python -m pip install -r requirements.txt` creates a local backend test environment.
- `.venv/bin/python -m pytest` runs the Telegram storefront backend tests.
- `USE_TESTCONTAINERS=1 .venv/bin/python -m pytest` runs backend tests against a disposable Postgres 16 container when Docker is available.
- `.venv/bin/alembic upgrade head` runs backend migrations using `backend/alembic`.
- `docker compose build && docker compose up -d` starts the production-shaped local/runtime stack.

## Project Structure

- `src/app/` contains client-side route selection and app host detection.
- `src/layout/` contains the shared site shell, header, footer, and age gate.
- `src/pages/` contains public route views.
- `src/content/` contains editable navigation, catalog, link, about, and findom data.
- `src/features/admin/` contains the local static-content admin editor.
- `src/styles/` contains grouped CSS for base, layout, pages, admin, and responsive rules.
- `tests/` contains route/content model tests and key frontend interaction coverage.
- `backend/app/` contains the FastAPI, Telegram bot, Stripe webhook, admin portal, and backend tests copied from `/srv/code/storefront`.
- `backend/alembic/`, `backend/deploy/`, and `backend/scripts/` contain migrations and deployment helpers for the storefront service.
- `assets/README.md` documents where production logo, banner, background, and thumbnail assets should be placed when available.
- `docs/hosting-note.md` documents hosting-policy considerations, Compose-first deployment assumptions, and intentional deviations from source references.

## Routes

- `/`
- `/videos`
- `/videos/custom`
- `/videos/customs`
- `/videos/main`
- `/findom`
- `/findom/auto-drains`
- `/findom/contracts`
- `/about`
- `/contact`
- `/privacy`
- `admin.hh88trance.com` routes to the backend admin portal with token login and a signed HTTP-only session cookie
- `/admin` renders the same portal only during local development and test runs

The Compose `web` container uses host-aware Nginx routing:

- `hh88trance.com` and `www.hh88trance.com` serve the public SPA so public deep links load through `index.html`.
- `serve.hh88trance.com` proxies API, catalog, purchase, webhook, and delivery-token traffic to internal backend containers.
- `admin.hh88trance.com` proxies only `/admin*` to the backend admin portal; other paths return `404`.

## Content And Hosting Notes

The source PDFs include explicit and protected-class hate references. The public site copy has been neutralized for public hosting. Do not reintroduce protected-class slurs, extremist praise, or demeaning protected-class content into production.

The website video pages poll the backend catalog at `/catalog` every 15 seconds and again when the tab regains focus. When the catalog is reachable, only active backend products are shown; if no active products exist, the pages show an empty state. If the catalog cannot be reached, the site falls back to the checked-in catalog arrays in `src/content/catalog.ts`.

Website purchase buttons point to the backend storefront redirect at `https://serve.hh88trance.com/buy/<product-slug>`. The backend validates that the product is active, creates a local pending order, opens a Stripe Checkout Session, and stores Stripe buyer/customer data from the verified webhook. Verified Stripe webhooks remain the only fulfillment path for access grants and delivery tokens.

Do not put `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, database URLs, bot tokens, or delivery secrets in frontend code. The website only needs the public storefront base URL at build time if the backend hostname differs from the browser origin:

```text
VITE_STOREFRONT_BASE_URL=https://serve.hh88trance.com
```

## Deployment

The main runtime is Docker Compose.

```bash
cp .env.example .env
chmod 600 .env
# edit .env
docker compose build
docker compose up -d
curl -fsS http://127.0.0.1:${WEB_HTTP_PORT:-8080}/ready
```

Default local URLs:

- Site/API entrypoint: `http://127.0.0.1:8080`
- Prometheus: `http://127.0.0.1:9090`
- Grafana: `http://127.0.0.1:3000`

Keep `.env` and provider secrets out of git. Keep `WEB_BIND` and `OBS_BIND` on `127.0.0.1` when a reverse proxy or tunnel publishes the site.

## Server Installation

To install the full repo to the existing private runtime boundary:

```bash
sudo backend/scripts/install_to_srv.sh
```

That script deploys the repository to `/srv/storebot/app`. Keep runtime secrets in `/srv/storebot/app/.env`; do not commit `.env` files.

The website video cards expect these backend product slugs:

```text
custom-4-mtx
custom-3-cdl
custom-2-ritual
custom-1-power
file-11
file-10
file-9
file-8
```

Use the backend admin portal or `python -m app.seed` from `/srv/storebot/app` to create active products with those exact slugs and attached delivery files. A website purchase link returns `404` until the matching product is active. The website catalog removes inactive products automatically after the next poll.

## Next Steps

For a non-technical owner, the safest workflow is to finish content first, then assets, then links, then launch checks.

1. Finalize the words on the site:
   - Read every page in the local Compose or Vite preview.
   - Note any wording that should change.
   - Ask a developer to update the matching file under `src/content/` or `src/pages/`.
2. Replace CSS-generated media with original production assets:
   - Logo or brand treatment assets if CSS text should be replaced.
   - Frame, grid, or background art if CSS-generated panels should be replaced.
   - Video stills or short preview clips for every card.
   - Ask a developer to place the files under `assets/` or `public/`, then connect them in the site.
3. Update the split content files with real external URLs:
   - Stripe payment links.
   - Cash App.
   - Throne.
   - Patreon.
   - Social/DM profiles.
   - Commission email or form destination.
4. Confirm the public edge:
   - Route `hh88trance.com`, `www.hh88trance.com`, `serve.hh88trance.com`, and `admin.hh88trance.com` to `http://127.0.0.1:${WEB_HTTP_PORT:-8080}` or the shared `hh88trance-web:8080` proxy target.
   - Keep Postgres, Prometheus, and Grafana bound to localhost unless intentionally exposed through private access.
5. Run a simple launch check against the Compose entrypoint:
   - Verify every route on desktop and mobile.
   - Confirm the 18+ gate persists as expected.
   - Confirm all external links open correctly.
   - Confirm preview media loads and is framed correctly.
6. Add stronger tests after URLs and assets are final:
   - Link integrity tests.
   - Accessibility checks.
   - Visual regression snapshots for the PDF-inspired layout.
7. Prepare launch metadata:
   - Final page titles and descriptions.
   - Social preview image.
   - Favicon and app icons.
   - Privacy/contact details with real business contact information.
8. After the preview is approved, rebuild and recreate the `web` and `api` containers, then point the production domain or tunnel at the Compose web entrypoint.
