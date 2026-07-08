# Hosting Note

This implementation is Compose-first. The `web` container serves the Vite React bundle through Nginx and applies hostname-based traffic routing:

- `hh88trance.com` and `www.hh88trance.com` serve the public site and SPA deep links.
- `serve.hh88trance.com` proxies storefront API paths such as `/catalog`, `/buy/*`, `/stripe/*`, `/telegram/*`, `/dl/*`, and `/download-file/*` to internal backend containers.
- `admin.hh88trance.com` proxies only `/admin*` to the backend admin portal.

Public copy remains sanitized for adult-oriented hosting risk. Any public deployment should avoid protected-class slurs, extremist praise, and demeaning copy. Keep payment processor rules separate from hosting rules because Stripe, Patreon, Cash App, Throne, and similar providers each have their own acceptable-use limits.

Payment buttons intentionally hit the backend `/buy/<slug>` redirect on `serve.hh88trance.com`. The site does not create orders directly, store card details, or fulfill files from frontend code. The video pages read display-safe active product metadata from `/catalog`; fulfillment still depends on verified Stripe webhooks and backend delivery-token generation.

## Intentional Deviations From PDF References

- Public copy has been neutralized to avoid slurs and protected-class hate references present in the PDFs.
- The repository did not include original logo, thumbnail, or background media. CSS-generated frame, rail, and still treatments approximate the layout and mood until production assets are supplied.
- Payment, social, and subscription URLs are marked as pending unless a safe public URL was available.
