# Changelog

## Unreleased

- Initialised the controlled MVP implementation from the approved documentation baseline.
- Added architecture decisions, implementation controls, traceability, security/compliance records, and operations/testing runbooks.
- Added the Tauri/React/FastAPI/SQLite local operating slice for campaigns and evidence-backed manual leads.
- Added authenticated loopback lifecycle, migrations, audit/stage events, backup/verification/isolated restore, and Windows packaging smoke tests.
- Applied the Etch ’N’ Shine universal application design tokens and accessible interaction states.
- Added the full desktop management shell, reusable design primitives, Lucide iconography, operational records, responsive layouts and visual-review evidence.
- Completed the local Stage 1 operating workflow, excluding CSV import by direction: campaign editing/pause/duplicate/search, full pipeline history, opportunity tracking, notes, follow-ups, communications, commercial statuses, suppression and privacy deletion.
- Added JSON/CSV lead and activity export, configurable operating defaults, diagnostics, dashboard queues, and backup create/verify controls.
- Added schema revision `0002_local_crm`, backend operation tests, seven frontend workflow tests, and real-browser acceptance evidence at desktop and compact widths.
- Kept external providers, AI, outbound messaging, and installer generation disabled for this development increment.
- Added schema revision `0003_qualification`, an editable local product catalogue, and a Shopify listing CSV upload interface with safe size/row limits and handle-based variant collapsing/upsert.
- Added versioned deterministic bakery scoring with seven visible category explanations, evidence/missing-data labels, manual override reasons, and rule-based product matches.
- Added campaign-capacity-aware weekly shortlist generation, suppression and repeat controls, visible selection reasons, and approve/defer/dismiss/replace actions.
- Integrated catalogue, scores, shortlists, and qualification metrics into the responsive dashboard and pipeline without enabling messaging or rebuilding an installer.
- Exposed campaign product categories and the 0–100 minimum shortlist score in both create and edit workflows, with case-insensitive category de-duplication and live shortlist propagation.
- Fixed desktop development startup by moving Cargo output out of Dropbox and making debug builds use the current source backend instead of a stale bundled sidecar.
- Added selected-file and import-progress feedback to Shopify catalogue upload; verified the supplied 589 KB export creates 123 products from 840 rows in under one second and re-imports without duplicates.
- Added accessible, filter-aware pagination to catalogue products, import issues, campaigns, leads, weekly recommendations, pipeline lead selection, open follow-ups and activity history. Catalogue pages show eight products with compact description previews.
