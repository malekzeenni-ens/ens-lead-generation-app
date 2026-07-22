# Test strategy

## Current release gates

| Layer | Gate | Current evidence |
|---|---|---|
| Python style/types | Ruff check/format and strict mypy | Pass |
| Backend behaviour | Pytest API/domain/security/backup integration suite | 14 passed; 92% statement coverage, including local CRM, Shopify catalogue import, versioned scoring, shortlists, suppression/privacy, export, tamper and active-restore rejection |
| Frontend | ESLint, TypeScript project build, Vitest/Testing Library | 13 passed; 71.17% aggregate coverage across the expanded workflow |
| Frontend production build | `tsc -b` and Vite build | Pass |
| Rust host | rustfmt, lifecycle test, Clippy warnings-as-errors | Pass; 1 lifecycle test |
| Sidecar | PyInstaller `onedir` process/health/database/cleanup smoke | Pass |
| Packaged host | Release executable starts bundled backend and authenticates health | Pass |
| Dependency baseline | Locked npm/uv resolution and npm high-severity audit | Pass; npm reports 0 vulnerabilities |

Run all non-packaging gates with `npm.cmd run quality`. Build/package smoke commands are documented separately because they are slower and generate ignored binaries.

## Covered invariants

- Loopback host validation and token-required API access.
- Health response and correlation-aware safe errors.
- Campaign validation/create/list/detail.
- Manual lead validation/create/list/detail and restart persistence.
- Exact duplicate-review response.
- Separate source observation, contact classification, initial pipeline event, and append-only audit evidence.
- SQLite migration from an empty database, WAL configuration, transaction rollback behaviour exercised by integration paths.
- Backup checksum/integrity and isolated restore; invalid/tampered paths fail safely.
- React accessible names and campaign create/edit request mapping, including minimum shortlist score and de-duplicated product categories.
- Desktop-shell landmarks/navigation, success feedback, evidence-backed lead request mapping, lead-to-pipeline handoff, stage/note operations, suppression, and settings.
- Campaign edit/status/duplicate/search, all pipeline stages, opportunity/commercial values, notes, follow-ups, manual communications and unified timelines.
- Suppression cancels open follow-ups, blocks outreach actions and retains minimised evidence after privacy deletion.
- JSON/CSV lead/activity export, formula-prefix protection, settings/summary/diagnostics and backup UI/API paths.
- Real-browser local workflow at 1366×768 and 720×600 with no horizontal overflow, clean console, and disposable data only.
- Desktop-owned backend startup, authenticated health, and shutdown.
- Shopify product-export CSV header/size/row validation, handle-based variant collapsing/upsert and editable catalogue records without raw-file retention.
- The supplied 589 KB Shopify export completes through the Tauri WebView in under one second: 840 rows become 123 products with no skips; repeat upload updates 123 and creates zero duplicates.
- Immutable scoring-profile versions, seven deterministic evidence/missing-data explanations, product-match snapshots and reasoned manual overrides.
- Weekly shortlist capacity, selection reasons, approve/defer/dismiss/replace decisions, recent-repeat prevention and suppression override/removal.
- Shared accessible pagination across catalogue/import issues, campaigns, leads, shortlist recommendations, pipeline lead selection, open follow-ups and activity events. Current pages clamp safely, filters reset to the first matching page, and a selected pipeline lead remains visible when its page changes.
- High-volume browser fixtures verified 123 products, 12 campaigns, 15 leads, 15 recommendations, seven open follow-ups and 23 activity events with bounded page sizes, keyboard-operable controls, zero application errors and no horizontal overflow at desktop and compact widths.
- Real-browser campaign create/edit verifies threshold persistence, category normalisation and shortlist propagation at desktop and compact widths.
- Real-browser catalogue/scoring/shortlist/dashboard workflow at 1366×768 and 720×600 with no page-level horizontal overflow and no application console errors; see `STAGE2_QUALIFICATION_REVIEW.md`.

## Required next tests

- UI tests for validation/error/loading/empty states, zoom behaviour, and keyboard navigation beyond the verified skip-link path.
- Automated visual-diff baselines; the current resolution and keyboard review is recorded in `DESIGN_SYSTEM_REVIEW.md`.
- Explicit migration revision upgrade/downgrade/forward-upgrade and prior-version fixtures.
- Installer clean-profile install, first run, upgrade, uninstall, data retention, and rollback.
- Lead CSV import formula/size/error cases only if lead import is returned to scope; it remains skipped by direction. Shopify product CSV bounds/header/upsert paths are covered; add broader Shopify export-version fixtures as real merchant examples become available.
- Additional frontend negative-path coverage for communication validation, privacy deletion confirmation, campaign editing, export failure, and backup failure.
- Later job restart/idempotency/budget tests, SSRF corpus, provider contracts, AI golden/schema/adversarial cases, and realistic-volume performance benchmarks.

Coverage is evidence, not the acceptance criterion. Tests must assert domain and safety outcomes; coverage thresholds may increase as each owning feature is added.
