# Admin Portal

The public React app contains a lightweight local content editor. It is rendered when the site is loaded from:

```text
admin.hh88trance.com
```

For local development and tests, it is also available while Vite runs in development mode at:

```text
/admin
```

## What It Does

The portal provides a browser-based editor for the checked-in public content model under `src/content/`:

- Custom and main video cards
- Payment, tribute, social, and contact links
- Recurring drain plans
- About-page accordion copy
- Launch-readiness checks for placeholder links and empty video fields

Drafts are saved to `localStorage` under `hh88-admin-content-v1`. This makes editing comfortable behind Cloudflare Access, but it does not publish changes by itself.

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

The current portal is a static client-side tool. It is suitable for launch status, public site content editing, and future admin module framing, but it must not store or expose customer data, payment data, commission details, credentials, or private files.

Cloudflare Access is the intended perimeter for `admin.hh88trance.com`. Before using it for real operations or automatic publishing, add server-side authentication and a private backend. Do not rely on client-side passwords or hidden routes for production access control.
