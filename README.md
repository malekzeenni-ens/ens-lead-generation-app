# Etch ’N’ Shine Lead Generation

A local-first Windows lead-intelligence workbench for controlled, evidence-backed prospecting. The product is intentionally not a scraper, mass outreach system or autonomous sending bot.

The current implementation provides the local operating workflow through operator-triggered campaign automation: editable campaigns, evidence-backed manual lead capture, the complete MVP pipeline, opportunity values, notes, follow-ups, manually confirmed communication history, suppression/privacy controls, exports, settings, diagnostics, and consistent backup/restore. Campaign controls configure discovery keywords/exclusions, radius, weekly capacity, a 0–100 minimum shortlist score, and product categories matched against the local catalogue. A campaign run refreshes every eligible lead against that campaign, reuses unchanged score inputs, calculates explained product matches, and prepares the current weekly shortlist without overwriting an existing one.

Google Places discovery is implemented as an optional official provider adapter. It is disabled until `ENS_GOOGLE_PLACES_API_KEY` is supplied to the backend environment and selected on a campaign. Results are capped, post-filtered to the exact campaign radius, staged with provider evidence, checked against suppression and exact/fuzzy duplicates, and safely enriched from up to three same-domain public pages before promotion. Google/website phone numbers, public emails and discovered social profiles are retained on the canonical lead with source evidence. Re-running discovery reuses the lead by provider ID, social handle, website, phone, email or exact identity instead of creating a duplicate.

Official Instagram profile enrichment is implemented through Meta's Facebook Login and Business Discovery path. Meta App credentials and tokens are protected for the current Windows user with DPAPI, never stored in SQLite or browser storage. In Social Leads, an operator can open a campaign hashtag, paste one relevant professional-profile URL, preview the public fields Meta exposes, and import it through the existing deduplication, scoring, product-matching and shortlist phases. A separate bulk action rechecks every Instagram handle already attached to a campaign's leads. Meta's hashtag-media response does not expose a dependable author identity for automatic new-lead creation, so hashtag links are explicitly an assisted discovery step rather than a scraper. Google Places, Instagram profile refresh and scoring-only refreshes remain separate actions. Consumer/private/unavailable profiles produce visible review errors, and the app does not automate a browser or initiate Instagram DMs. Lead CSV import remains deliberately skipped; AI inference and outbound sending remain disabled.

The Shopify interface accepts a standard Shopify product export (maximum 5 MB / 10,000 rows), collapses variants by `Handle`, and creates or updates local catalogue records. The raw CSV is read in the browser and is not retained. Optional Shopify tags can supply `segment:`, `use-case:`, and `sample-eligible` metadata; every imported product remains editable in the catalogue. Long registers are paginated throughout the workbench; catalogue pages show eight products, reset safely when searched, and keep full descriptions available in the product editor.

See:

- `docs/operations/LOCAL_SETUP.md`
- `docs/implementation/IMPLEMENTATION_PLAN.md`
- `docs/implementation/REQUIREMENTS_TRACEABILITY.md`
- `docs/architecture/SECURITY_MODEL.md`

## Quick start

On Windows, double-click `Start Etch N Shine.cmd` in the repository root after completing the one-time dependency setup. The launcher starts the desktop development app from the correct folder and keeps startup errors visible.

```powershell
uv sync --all-packages --dev --locked
npm.cmd ci
npm.cmd run quality
npm.cmd run desktop:dev
```

`desktop:dev` is a development host: it starts the frontend and backend services and does not build or require an installer. The frontend and backend can also be run as separate development servers; see `docs/operations/LOCAL_SETUP.md`.

An installer is only an optional distribution step for a future Windows release. It is not part of the current development loop and was not rebuilt for this increment.
