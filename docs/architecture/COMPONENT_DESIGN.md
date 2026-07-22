# Component design

**Updated:** 18 July 2026

## Runtime components

| Component | Responsibility | Must not own |
|---|---|---|
| Tauri host | Process lifecycle, random port/token, backend connection IPC, packaged smoke test | Domain rules, provider credentials, data writes |
| React frontend | Accessible operator forms, lists, loading/error/empty states | Secrets, authoritative validation, direct database access |
| FastAPI API | Authenticated transport, validation, correlation IDs, stable error contract | Provider-specific business rules |
| Domain services | Campaign/lead/pipeline/compliance/catalogue/scoring/shortlist invariants, transactions, duplicate-review decisions, audit events | HTTP or UI concerns |
| Repositories | SQLAlchemy queries and persistence | Policy decisions |
| Alembic | Ordered schema evolution | Runtime data repair without a migration |
| Backup service | SQLite-native copy, integrity check, checksum manifest, isolated restore | Live database replacement |

The backend is a modular monolith. Domain modules live under `app/domains`; API routers translate transport models to services. This retains simple local deployment while preserving seams for campaign, lead, evidence, compliance, jobs, integrations, AI, outreach, and analytics modules.

## Request path

1. Tauri starts the backend on `127.0.0.1` with an ephemeral port and 256-bit-class session token.
2. React asks the host for `baseUrl` and `sessionToken` through `backend_connection`.
3. The API client sends `X-Session-Token` and a correlation ID.
4. FastAPI validates authentication and Pydantic schemas.
5. A domain service performs one short transaction and appends audit/stage evidence in the same unit of work.
6. Responses use typed JSON. Failures use `code`, `message`, `details`, and `correlation_id`.

## Implemented use cases

- Create/list/detail/edit/pause/resume/duplicate/search campaigns.
- Create/list/detail/edit/search/filter manually researched leads.
- Require a website or social profile and capture source name, URL, classification, method, and collection time separately from canonical lead fields.
- Associate a lead to a campaign, create its initial `new` stage event, and append an audit event atomically.
- Flag an exact normalised business-name/location match for duplicate review.
- Move leads through the complete local pipeline with immutable stage history, values, lost reasons, and mock-up/sample/quote statuses.
- Add notes, dated typed follow-ups, completions, manually confirmed communications, replies, and a chronological activity timeline.
- Enforce suppression by moving to Do Not Contact, cancelling open follow-ups, blocking new outreach actions, and retaining minimised suppression evidence after privacy deletion.
- Export lead/activity data as JSON or formula-safe CSV and expose authenticated settings, dashboard summary, and diagnostics.
- Create, verify, and restore SQLite backups to an isolated path.
- Upload a Shopify product-export CSV through the catalogue interface; validate file/row limits, collapse variants and upsert editable products by handle without retaining the raw file.
- Create immutable bakery scoring-profile versions; calculate and preserve explained deterministic score runs and reasoned manual overrides.
- Match active products to leads through visible segment/campaign rules and snapshot the match evidence with each score/shortlist decision.
- Generate one campaign shortlist per week within capacity while enforcing suppression, stage, score, freshness and recent-recommendation controls; approve, defer, dismiss or replace individual items.

## UI composition

The interface uses the universal management-application shell: a 56px application header, 240px navigation sidebar, scroll-contained main workspace, and 28px status bar. The overview exposes local operating metrics, follow-up queues, a simplified pipeline, product/scoring counts, and the current weekly shortlist. Campaign, lead, pipeline, catalogue, weekly-shortlist, and settings workspaces pair compact forms with operational records. Lead records use a table at desktop sizes and labelled card rows on compact screens.

Reusable React primitives in `components/DesignSystem.tsx` own connection status, navigation items, section headings, metrics, empty states, and loading states. Lucide is the sole production icon family. Semantic colour, type, spacing, radius, control-height, transition, and surface tokens are centralised in `styles.css`; component markup contains no raw presentation colours.

Native controls preserve keyboard behaviour. The shell provides a skip link, one banner/navigation/main landmark sequence, visible focus, live loading/success/error feedback, textual status alongside colour, reduced-motion support, and approximately 36px minimum targets. Errors retain actionable retry and correlation references.

## Extension rules

- Add an owning domain module before adding provider code.
- Put provider mapping behind a neutral adapter port.
- Add a migration for every schema change.
- Create durable job state before scheduled or retrying work.
- Add suppression checks at shortlist, draft, approval, and send boundaries, not only in UI.
- External failures must leave manual local workflows available.
