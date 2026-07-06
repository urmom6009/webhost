# Admin Portal

The admin portal is rendered when the site is loaded from:

```text
admin.hh88trance.com
```

For local development and tests, it is also available while Vite runs in development mode at:

```text
/admin
```

## What It Does

The portal provides a browser-based editor for the static content model in `src/content.ts`:

- Custom and main video cards
- Payment, tribute, social, and contact links
- Recurring drain plans
- About-page accordion copy
- Launch-readiness checks for placeholder links and empty video fields

Drafts are saved to `localStorage` under `hh88-admin-content-v1`. This makes editing comfortable behind Cloudflare Access, but it does not publish changes by itself.

Use the **Export** tab to copy or download the edited JSON and generated TypeScript array bodies. To publish the update, apply the generated arrays to `src/content.ts`, run tests/build, commit, and deploy.

## Vercel Setup

1. Deploy this repository as the main HH88TRANCE Vercel project.
2. In the Vercel project dashboard, add `admin.hh88trance.com` under **Settings > Domains**.
3. Point the DNS record for `admin.hh88trance.com` to Vercel using the value Vercel provides.
4. Keep `vercel.json` as-is. The existing SPA rewrite sends the admin hostname to `index.html`, and the React app switches to the admin portal by hostname.

## Security Boundary

The current portal is a static client-side tool. It is suitable for launch status, public site content editing, and future admin module framing, but it must not store or expose customer data, payment data, commission details, credentials, or private files.

Cloudflare Access is the intended perimeter for `admin.hh88trance.com`. Before using it for real operations or automatic publishing, add server-side authentication and a private backend. Do not rely on client-side passwords or hidden routes for production access control.
