# Stage 2 qualification review

**Review date:** 19 July 2026  
**Result:** Pass for the catalogue, deterministic qualification, weekly shortlist, dashboard and suppression slice

## Scope

This review covered the user-directed development items: product catalogue/matching, deterministic explained scoring, weekly shortlist generation, and dashboard/pipeline integration. It also covered the requested Shopify listing CSV upload interface. Lead CSV import, provider discovery, AI inference, Shopify API synchronisation, outbound sending and installer generation were not in scope.

## Disposable acceptance data

- One active bakery campaign with weekly capacity three.
- Three manually entered leads with public website evidence.
- `shopify-products-sample.csv`: three Shopify rows representing two products, including a second variant row for the same handle.
- One product catalogue and one bakery scoring profile version.
- A separate disposable pagination fixture with 123 merchant products, 12 campaigns, 15 leads, 15 recommendations, seven open follow-ups and 23 activity events.
- No production database, credentials, provider request or external message.

## Browser workflow

| Check | Outcome |
|---|---|
| Upload Shopify listing CSV | Pass: local file control accepted the sample; the API reported the import and produced two catalogue products from three rows |
| Real merchant Shopify export | Pass: `products_export_1-19072026.csv` completed through the Tauri WebView in 0.817 seconds; 840 rows produced 123 products with zero skips; a second 0.837-second pass updated all 123 with zero duplicates |
| Shopify normalisation | Pass: variants were collapsed by handle; target-segment/use-case/sample tags and price/image metadata were normalised into editable products |
| Bakery scoring | Pass: visible weights totalled 100; the pipeline calculated a versioned score with seven category totals and rule version |
| Score explanation | Pass: the full accessibility tree exposed awarded points and expandable evidence/missing sections; AI was explicitly not used |
| Product matching | Pass: both products matched by deterministic segment/category rules with a visible reason and rule-based label |
| Campaign qualification controls | Pass: create persisted a 65/100 minimum and de-duplicated categories; edit changed them to 70/100 and new categories; the shortlist screen immediately displayed the revised threshold |
| Weekly generation | Pass: three ranked leads were generated within campaign capacity with score, contact route, matched products and pipeline reasons |
| Operator decisions | Pass: approve and defer persisted; deferred work left the active dashboard queue |
| Dashboard integration | Pass: active products, scored leads, shortlist count and actionable items updated after each operation |
| Suppression override | Pass: applying Do Not Contact moved the lead to the protected stage, disabled score/stage/follow-up outreach actions, suppressed the shortlist item and reduced the active shortlist from two to one |
| Messaging boundary | Pass: shortlist copy states that no action sends a message; controlled-mode labels remained visible |
| High-volume pagination | Pass: catalogue 8/page, campaigns 6/page, leads and recommendations 10/page, pipeline selector 8/page, open follow-ups 5/page and activity events 10/page; search reset/clamping and page transitions were verified |

## Responsive and accessibility review

- At 1366×768 the catalogue and dashboard retained the desktop shell, readable hierarchy, keyboard-focus treatment and balanced two-column forms/cards.
- At 720×600 primary navigation became a horizontally scrollable compact navigation row; the document itself had no horizontal overflow.
- Semantic regions, headings, labels, required states, status announcements and button names were exposed to the accessibility tree.
- The browser reported no application errors. Console output contained only Vite connection and React development messages.
- Pagination controls exposed labelled navigation landmarks, current-page state, bounded result summaries and keyboard-operable previous/next controls. The catalogue had no horizontal overflow at either reviewed viewport.

Visual evidence:

- `screenshots/stage2-dashboard-1366x768.png`
- `screenshots/stage2-catalogue-1366x768.png`
- `screenshots/stage2-shortlist-720x600.png`
- `screenshots/stage2-campaign-controls-1366x768.png`
- `screenshots/stage2-campaign-controls-720x600.png`
- `screenshots/real-shopify-import-123-products.png`
- `screenshots/pagination-catalogue-page-controls-1366x768.png`
- `screenshots/pagination-catalogue-page-controls-720x600.png`
- `screenshots/pagination-catalogue-filtered-1366x768.png`

## Automated gates

- `npm.cmd run quality`: pass.
- Python: Ruff/format and strict mypy pass; 14 tests pass with 92% statement coverage.
- Frontend: ESLint, strict TypeScript, 13 Vitest/Testing Library tests, production build; 71.17% aggregate statement coverage.
- Rust host: rustfmt, lifecycle test and Clippy with warnings denied pass.
- npm high-severity dependency audit: zero vulnerabilities.

## Residual work

Per-lead add/remove/reorder editing of recommended products (FR-054), additional segment scoring defaults, evidence resolution/identity merge, discovery adapters, AI, drafts/approval/outbound communication and broader analytics remain later controlled increments. Production outreach remains prohibited pending CMP-005 legal/business decisions and future boundary-specific suppression tests.
