# HH88TRANCE

Vercel-ready React site plus the Telegram storefront backend for the HH88TRANCE adult audio/video brand.

The first implementation follows the provided PDF references from `/Users/colinvargas/Downloads/HH88Trance-Web` for page structure, dark starfield styling, neon navigation, card density, and adult-brand tone. Public copy is intentionally sanitized for Vercel hosting risk.

## Tech Stack

- Vite
- React
- TypeScript
- Vitest and Testing Library
- ESLint
- Vercel static hosting with SPA rewrites
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
- `docs/hosting-note.md` documents Vercel policy considerations and intentional deviations from the PDF references.

## Routes

- `/`
- `/videos`
- `/videos/customs`
- `/videos/main`
- `/findom`
- `/findom/auto-drains`
- `/findom/contracts`
- `/about`
- `/contact`
- `/privacy`
- `admin.hh88trance.com` renders the private admin portal for static content editing
- `/admin` renders the same portal only during local development and test runs

The site uses client-side routing with `vercel.json` rewrites so deep links load through `index.html`.

## Content And Hosting Notes

The source PDFs include explicit and protected-class hate references. The public site copy has been neutralized so it is more suitable for Vercel review and public hosting. Do not reintroduce protected-class slurs, extremist praise, or demeaning protected-class content into a Vercel production deployment.

The static website video purchase buttons point to the backend storefront redirect at `https://api.hh88trance.com/buy/<product-slug>`. The backend validates that the product is active, opens the matching Telegram bot deep link, and the bot then creates the Stripe Checkout Session. Verified Stripe webhooks remain the only fulfillment path for access grants and delivery tokens.

Do not put `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, database URLs, bot tokens, or delivery secrets in Vercel frontend environment variables. The website only needs the public storefront base URL if the backend hostname changes:

```text
VITE_STOREFRONT_BASE_URL=https://api.hh88trance.com
```

## Deployment

These steps assume this is your first time using Vercel and that you want the simplest path: connect GitHub, import the site, and let Vercel publish it for you.

### Before You Start

You need:

- A GitHub account.
- A Vercel account. You can sign up at https://vercel.com with the same GitHub account.
- The finished version of this repository pushed to GitHub.
- Final links for any payment, social, email, or commission buttons you want visitors to use.

### First-Time Vercel Steps

1. Create or sign in to your Vercel account at https://vercel.com.
2. Choose **Add New...** and then **Project**.
3. Connect your GitHub account if Vercel asks for permission.
4. Select the GitHub repository for this website.
5. On the import screen, Vercel should detect this as a Vite project. Keep these settings:
   - Build command: `npm run build`
   - Output directory: `dist`
   - Install command: `npm install`
6. Leave environment variables blank unless a future feature specifically requires them. Optional: set `VITE_STOREFRONT_BASE_URL` only if the backend is not `https://api.hh88trance.com`.
7. Click **Deploy**.
8. Wait for Vercel to finish the build. If it succeeds, Vercel will show a live preview URL.
9. Open the preview URL and click through every page before sharing it publicly.

### After Deployment

- If the site looks right, use the Vercel dashboard to add a custom domain when ready.
- If Vercel reports a build error, read the first red error message in the deployment log and fix that issue before redeploying.
- Every time you push a new change to the GitHub repository, Vercel will automatically build and publish a fresh version.
- The repository workflow `.github/workflows/vercel-deploy.yml` deploys every non-`main` branch and every pull request as a Vercel Preview deployment after tests pass. A push or merged pull request that updates `main` deploys Production after the same validation gate passes.
- Keep `.vercel/`, local `.env` files, and provider secrets out of git.
- Replace pending payment/social placeholders before a production launch.
- Confirm every active website video card has a matching active backend product slug before launch.
- Review `docs/hosting-note.md` before publishing any less-sanitized copy.
- Add both `hh88trance.com` and `admin.hh88trance.com` to the same Vercel project. The app detects the admin hostname and renders the admin portal there.
- Put `admin.hh88trance.com` behind Cloudflare Access before sharing it. The portal stores drafts locally and exports JSON/TypeScript for updating `src/content.ts`; it does not publish changes automatically without a future backend.

### GitHub Secrets For Vercel

Add these repository secrets in GitHub before relying on automatic deploys:

```text
VERCEL_TOKEN
VERCEL_ORG_ID
VERCEL_PROJECT_ID
```

`VERCEL_ORG_ID` and `VERCEL_PROJECT_ID` come from `.vercel/project.json` after running `vercel link` locally, or from the Vercel project settings. Do not commit `.vercel/project.json`; the workflow creates it from secrets during each run.

## Backend Deployment

The cloneable backend source is under `backend/`. To install it to the existing private runtime boundary:

```bash
sudo backend/scripts/install_to_srv.sh
```

That script deploys the backend subtree to `/srv/storebot/app`. Keep runtime secrets in `/srv/storebot/app/.env`; do not commit `.env` files.

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

Use the backend admin portal or `python -m app.seed` from `/srv/storebot/app` to create active products with those exact slugs and attached delivery files. A website purchase link returns `404` until the matching product is active.

## Next Steps

For a non-technical owner, the safest workflow is to finish content first, then assets, then links, then launch checks.

1. Finalize the words on the site:
   - Read every page in the Vercel preview.
   - Note any wording that should change.
   - Ask a developer to update the matching text in `src/content.ts` or `src/App.tsx`.
2. Replace CSS-generated media with original production assets:
   - Logo and money-banner header art.
   - Starfield/ring background art.
   - Video stills or short preview clips for every card.
   - Ask a developer to place the files under `assets/` or `public/`, then connect them in the site.
3. Update `src/content.ts` with real external URLs:
   - Stripe payment links.
   - Cash App.
   - Throne.
   - Patreon.
   - Social/DM profiles.
   - Commission email or form destination.
4. Decide the final hosting platform:
   - Use Vercel only with sanitized public copy.
   - Choose a more adult-content-tolerant host if the final brand requires explicit copy that Vercel may reject.
5. Run a simple launch check in the Vercel preview:
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
8. After the preview is approved, share the Vercel URL or connect a custom domain from the Vercel dashboard.
