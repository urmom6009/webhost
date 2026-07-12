# Admin Portal

Production admin traffic is handled by the backend admin portal, not the public React app. It is served from:

```text
admin.hh88trance.com
```

The portal requires `ADMIN_PORTAL_TOKEN`, sets a signed HTTP-only session cookie, and should be kept behind the admin hostname and any edge access policy you enable.

The production file browser is locked to `/mnt/storefront-media`. The API container mounts that host directory read-write, and the downloads container mounts the same directory read-only. Storage keys shown in the portal are relative to `/mnt/storefront-media`; paths outside that directory and symlinks are not browsable from the portal.

Each file row can start a new draft product with the storage key prefilled. Save the product as a draft first, review the preview/edit screen, then enable **Active in catalog** when the title, price, delivery file, and Stripe checkout state are ready. Only active products appear in `/catalog` and Telegram `/catalog`.

For local development and tests, the static React content editor is still available while Vite runs in development mode at:

```text
/admin
```

## Local Static Editor

The local static editor provides a browser-based editor for the checked-in public content model under `src/content/`:

- Custom and main video cards
- Payment, tribute, social, and contact links
- Recurring drain plans
- About-page accordion copy
- Launch-readiness checks for placeholder links and empty video fields

Drafts are saved to `localStorage` under `hh88-admin-content-v1`. This does not publish changes by itself.

Use the **Export** tab to copy or download the edited JSON and generated TypeScript array bodies. To publish the update, apply the generated arrays to the matching split file, run tests/build, commit, rebuild the Compose images, and deploy.

Target files:

- Videos: `src/content/catalog.ts`
- Links: `src/content/links.ts`
- About accordion copy: `src/content/about.ts`
- Recurring drain plans: `src/content/findom.ts`

## Compose Setup

The main runtime is Docker Compose. The public `web` container serves the React bundle and proxies backend paths to internal services. After content changes:

```bash
npm run lint
npm test
npm run build
docker compose build web
docker compose up -d web
```

If backend catalog behavior changed, rebuild and recreate `api` as well:

```bash
docker compose build api
docker compose up -d api
```

## Security Boundary

The production admin hostname routes to the backend portal under `/admin*`. Do not expose the local static editor on the production admin hostname, and do not store customer data, payment data, commission details, credentials, or private files in the static editor.
