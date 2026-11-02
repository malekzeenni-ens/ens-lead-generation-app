# ADR-026: Catalogue sync from the Shopify Admin API

- **Status:** Accepted (operator decision, 2 November 2026)
- **Context:** The catalogue was refreshed by exporting a CSV from Shopify admin and uploading it. The Shopify-to-Etsy app already syncs the same store through the Admin API with a Shopify custom app, and the operator asked to reuse that rather than build something new.
- **Decision:** Copy the Shopify-to-Etsy app's client (`backend/app/integrations/shopify/admin_api.py`) into `app/domains/catalogue/shopify_admin.py`, as close to the source as possible, and connect with the same custom app and the same credential rule as its `build_shopify_client_from_env`: an access token if one is set, otherwise the client ID and secret exchanged for a token. A sync is a background job (ADR-022) that feeds the fetched products into the same apply step as a CSV import.
- **Alternatives considered:** Importing the Etsy app's latest snapshot CSV from disk (it lacks product category and SEO description, and depends on that app having synced); calling the Etsy app's HTTP sync (it would have to be running); a new client written from scratch (duplicates tested code).

## Differences from the copied client

- Reads `category { fullName }` and `seo { description }`, which this app uses for categories and summaries.
- Five products per page instead of one. Each page asks for up to 25 images and 100 variants, so five products cost about 630 of Shopify's 1,000-point query limit. The live sync took 8.6 seconds for 132 products.
- The CSV, JSON and Globo writers are left out.

## Credentials

Stored in the DPAPI vault under `shopify_credentials` (store, API version, client ID and secret or access token), entered in Settings → Connections → Shopify. On 2 November 2026 they were copied once from the Shopify-to-Etsy app's `.env`, without being displayed. Responses never include them. Only product read access is used.

## Consequences

- A sync and a CSV import of the same products leave identical catalogues (tested), including wording protection, knowledge-pack re-application and retiring products no longer in Shopify. Products from both keep `source = shopify_csv`, so no migration was needed.
- Globo option-set helper products (`option-set-…`) come through, as they already did from the CSV export.
- The Shopify-to-Etsy app and this one now carry the same client code; a fix in one should be carried to the other.
- Sync, connection changes and the connection test are desktop-only (ADR-025 route policy).
