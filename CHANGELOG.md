# Changelog

## 2026-07-08

- Restyled the public site around the refined dark catalog preview: framed header, hard-edged panels, steel grid rails, red status accents, and consistent video-card language across public routes.
- Added live website catalog behavior backed by the FastAPI `/catalog` endpoint, with static fallback and no-files empty states.
- Removed unused top-level compatibility shims for `src/AdminPortal.tsx` and `src/content.ts`; content now lives under split modules in `src/content/`.
- Updated README, hosting notes, admin docs, asset guidance, backend docs, and runbook entries for Compose-first deployment, split content files, and live catalog smoke checks.

## 2026-05-29

- Added first-time Vercel deployment steps and low-code launch next steps to the README.
- Expanded the README with setup, structure, deployment, hosting notes, and detailed next steps.
- Scaffolded the Vercel-ready HH88TRANCE React site with all requested public routes.
- Added shared header, navigation, cards, accordions, link rows, 18+ gate, privacy content, and sanitized adult-brand copy.
- Documented hosting-policy constraints, missing production assets, and pending external payment/social URLs.
