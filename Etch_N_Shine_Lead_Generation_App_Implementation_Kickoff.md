# Etch ’N’ Shine Lead Generation App
## Coding Agent Implementation Kickoff and Delivery Guardrails

**Document type:** Implementation execution prompt  
**Audience:** Senior coding agent / autonomous software engineering agent  
**Business owner:** Etch ’N’ Shine  
**Target platform:** Windows local-first desktop application  
**Source requirements:** Etch ’N’ Shine Lead Generation App BRD/FSD v1.0  
**Architecture baseline:** Approved Solution Architecture Assessment and Solution Architect Review outputs  
**Implementation status:** Start of controlled MVP delivery  
**Date:** 18 July 2026

---

# 1. Your Role

Act as a **principal software engineer, solution architect, security engineer, data engineer, QA lead, and Windows desktop deployment specialist**.

Your responsibility is to implement the Etch ’N’ Shine Lead Generation App as a secure, maintainable, local-first lead-intelligence and controlled-outreach application.

You must convert the approved requirements and architecture into production-quality software while preserving the following product principles:

1. Lead quality over lead volume.
2. Explainability over opaque automation.
3. Human approval over autonomous outreach.
4. Evidence-backed facts over AI invention.
5. Modularity over provider lock-in.
6. Local ownership of business data.
7. Low operating complexity.
8. Compliance-aware prospecting.
9. Safe recovery from external failures.
10. Phased delivery rather than uncontrolled scope expansion.

The product is **not** an autonomous lead-generation bot, mass outreach engine, social-media scraper, enterprise CRM, or unattended marketing automation platform.

---

# 2. Authoritative Inputs

Before writing or changing code, read the following source documents in full:

1. `Etch_N_Shine_Lead_Generation_App_BRD_FSD(1).md`
2. `Etch_N_Shine_Solution_Architect_Review_Prompt.md`
3. `Etch_N_Shine_Lead_Generation_Architecture_Assessment.md`
4. This implementation kickoff document.

Use the BRD/FSD as the source of business and functional requirements.

Use the architecture assessment as the binding technical baseline, including its scope amendments, data-model refinements, security requirements, phasing decisions, architecture decision register, and implementation roadmap.

Where the documents conflict, apply the following precedence:

1. Safety, legal, privacy, platform-policy, and security constraints.
2. Architecture assessment decisions and amendments.
3. BRD/FSD business requirements.
4. This implementation sequencing plan.
5. Agent implementation preferences.

Do not silently reinterpret or discard requirements. Record any material conflict or necessary deviation in an Architecture Decision Record before implementation.

---

# 3. Mandatory First Action: Existing Repository Assessment

Do not immediately generate a new application or replace an existing codebase.

First inspect the entire repository and produce a concise implementation baseline covering:

- repository structure;
- existing frontend and backend technologies;
- current application entry points;
- current database and migration approach;
- configuration and secret handling;
- installed dependencies and lockfiles;
- existing tests and test coverage;
- linting, formatting, and type-checking configuration;
- build and packaging scripts;
- existing CI workflows;
- current Windows support;
- current implemented requirements;
- partially implemented requirements;
- conflicting or unsafe implementation decisions;
- reusable components;
- obsolete or duplicate code;
- known technical debt;
- data-loss or regression risks.

Create or update:

```text
docs/implementation/BASELINE_ASSESSMENT.md
```

The baseline assessment must include a requirement-to-code traceability matrix.

If no repository exists, initialise one using the approved target architecture and clearly record that the project started from a clean baseline.

Do not delete working functionality merely because a different implementation would be cleaner. Refactor incrementally and protect behaviour with tests.

---

# 4. Approved Architecture Baseline

Implement the MVP as a **local-first modular monolith**.

## 4.1 Target technology stack

Preferred stack:

- **Desktop host:** Tauri.
- **Frontend:** React with TypeScript.
- **Frontend build tooling:** Vite or the repository’s equivalent supported build system.
- **Backend/API:** Python with FastAPI.
- **Domain and validation:** Pydantic models and explicit service-layer validation.
- **ORM/data access:** SQLAlchemy 2.x or an equivalent explicit repository approach.
- **Database:** SQLite in WAL mode.
- **Database migrations:** Alembic.
- **Background processing:** Persistent SQLite-backed jobs executed by a local worker.
- **Secret storage:** Windows Credential Manager or DPAPI-protected vault.
- **Testing:** Pytest for Python; Vitest and React Testing Library for frontend; Playwright for end-to-end tests.
- **Static analysis:** Ruff, mypy or pyright, ESLint, TypeScript strict mode.
- **API contract:** OpenAPI generated by FastAPI, with generated or typed frontend API clients where practical.
- **Packaging:** Signed-capable Windows installer architecture through Tauri.

A deviation from this stack is permitted only when:

- the existing repository already uses a materially equivalent, maintainable stack;
- changing it would create disproportionate risk;
- the deviation preserves all required architecture and security controls;
- the rationale is documented in an ADR.

## 4.2 Runtime processes

The intended runtime consists of:

1. Tauri desktop host.
2. React/TypeScript user interface.
3. FastAPI process bound to loopback only.
4. Persistent local worker process or controlled worker execution mode.
5. SQLite database.
6. Windows-native credential storage.
7. Rotating structured logs.

The Tauri host must manage backend process start, health checks, controlled shutdown, and failure reporting.

## 4.3 Mandatory local-network rule

The backend must bind to:

```text
127.0.0.1
```

It must not bind to `0.0.0.0` by default.

Use an ephemeral session token or equivalent application-session control between the desktop host/frontend and local API.

Never expose the local API to the LAN without a separate, explicit, security-reviewed feature.

---

# 5. Non-Negotiable Guardrails

The following constraints are release-blocking.

## 5.1 No autonomous external communication

The MVP must not:

- automatically send emails;
- automatically send Instagram DMs;
- automatically send Facebook messages;
- run unattended outreach sequences;
- change a draft to sent without explicit user confirmation;
- contact a suppressed lead;
- send an edited draft under an earlier approval.

All external communication must require a specific, auditable user approval.

Editing approved content must invalidate its approval.

## 5.2 No automated Meta scraping or bot behaviour

The MVP must not:

- automate Instagram or Facebook login;
- scrape authenticated Meta pages;
- automate scrolling or profile extraction;
- automate DMs;
- bypass platform access controls;
- emulate user behaviour to avoid platform limits;
- make broad automated Meta discovery a dependency.

Implement assisted search and manual capture only unless an approved official API integration is separately validated and authorised.

## 5.3 Deterministic numeric scoring

The lead score must be calculated by deterministic, versioned rules.

AI may:

- summarise evidence;
- recommend product fit;
- propose an outreach angle;
- draft outreach;
- explain a deterministic score.

AI must not be the authoritative source of the final numeric score in the MVP.

## 5.4 Evidence-based AI

AI output must not invent:

- contact names;
- business facts;
- events;
- customer needs;
- relationships;
- purchase intent;
- contact information;
- unsupported compliments;
- prices, discounts, capacity, lead times, or sample promises.

Every AI task must use a compact evidence packet with stable evidence identifiers.

Structured output must be validated. Unknown evidence identifiers or unsupported claims must cause rejection or visible review warnings.

## 5.5 Durable jobs only

Do not use an in-memory scheduler as the source of truth for discovery, enrichment, AI, backup, or scheduled work.

All jobs must be persisted with:

- unique ID;
- job type;
- idempotency key;
- state;
- scheduled timestamp;
- attempts;
- lease owner and expiry;
- checkpoint/progress;
- retry classification;
- redacted error information;
- creation/start/completion timestamps;
- cancellation state.

## 5.6 No unsafe website crawler

Website enrichment must be narrow, controlled, rate-limited, and policy aware.

It must not become a general crawler.

Implement SSRF protection before enabling external website fetching.

## 5.7 No secrets in source or frontend

Never store API keys, OAuth refresh tokens, passwords, or provider secrets:

- in frontend code;
- in localStorage;
- in source-controlled `.env` files;
- in SQLite as plaintext;
- in logs;
- in error messages;
- in exported diagnostics.

Store only non-sensitive references and metadata in the database.

## 5.8 No destructive schema changes without migration and backup

Every schema change must use a versioned migration.

Never mutate production data structures ad hoc.

Before destructive or irreversible migrations:

- create a verified backup;
- provide rollback or recovery instructions;
- test migration on representative data;
- record the change in the migration log.

---

# 6. Required Engineering Principles

## 6.1 Modular monolith boundaries

Organise the backend into clear domain modules such as:

```text
app/
  api/
  core/
  db/
  domains/
    campaigns/
    leads/
    discovery/
    evidence/
    identity/
    scoring/
    products/
    recommendations/
    shortlist/
    outreach/
    approvals/
    communications/
    pipeline/
    followups/
    compliance/
    analytics/
    jobs/
    backups/
    integrations/
    ai/
  infrastructure/
  security/
  observability/
```

Avoid circular dependencies.

Domain logic must not depend directly on UI components or provider SDKs.

External providers must be accessed through application-owned interfaces.

## 6.2 Separation of concerns

Maintain clear separation between:

- API/controller layer;
- application services/use cases;
- domain logic;
- repositories/data access;
- provider adapters;
- background jobs;
- security controls;
- UI state and presentation.

Do not place business rules in route handlers or React components.

## 6.3 Provider abstraction

Create provider-neutral interfaces for:

- discovery sources;
- website enrichment;
- geocoding;
- AI completion;
- email integration;
- product-catalogue integration;
- secret storage.

No provider-specific response model may leak into the core domain model.

## 6.4 Feature flags

Use feature flags or configuration gates for:

- Google discovery;
- website enrichment;
- AI provider;
- scheduled discovery;
- Windows Task Scheduler integration;
- Zoho draft integration;
- Zoho sending;
- Shopify synchronisation;
- experimental segment scoring.

Disabled features must degrade safely and visibly.

## 6.5 Idempotency

All retryable operations must be idempotent or protected by an idempotency mechanism.

This includes:

- candidate imports;
- discovery runs;
- enrichment steps;
- AI tasks;
- shortlist generation;
- backup creation;
- future Zoho draft creation;
- future external send actions.

---

# 7. Required Repository Structure and Project Controls

Establish or align the repository to a clear structure such as:

```text
/
  apps/
    desktop/
    frontend/
    backend/
    worker/
  packages/
    shared-types/
    api-client/
    ui-components/
  migrations/
  tests/
    unit/
    integration/
    contract/
    e2e/
    fixtures/
  docs/
    architecture/
    implementation/
    operations/
    testing/
    compliance/
    adr/
  scripts/
  .github/
  README.md
  SECURITY.md
  CONTRIBUTING.md
  CHANGELOG.md
```

A simpler structure is acceptable where it remains explicit and maintainable.

At minimum, add:

- dependency lockfiles;
- reproducible local setup commands;
- `.env.example` containing no real secrets;
- formatting and linting configuration;
- strict TypeScript configuration;
- Python type-checking configuration;
- automated tests;
- pre-commit or equivalent validation;
- migration commands;
- seed/demo-data commands;
- backup and restore commands;
- build and installer commands;
- architecture and operations documentation.

---

# 8. Data Architecture Requirements

## 8.1 Database baseline

Use SQLite with:

- WAL mode;
- foreign-key enforcement;
- busy timeout;
- short transactions;
- explicit indexes;
- migrations;
- integrity checks;
- checkpoint-aware backup;
- FTS5 where justified.

Do not blindly copy an active database file for backup.

Use the SQLite backup API or an equivalent consistency-safe mechanism.

## 8.2 Required conceptual entities

Implement or formally map the following entities.

### Canonical business entities

- `lead`
- `business_identity`
- `business_location`
- `contact_point`
- `lead_campaign`
- `lead_stage_event`
- `lead_note`

### Acquisition and evidence

- `source_system`
- `discovery_run`
- `discovery_candidate`
- `source_observation`
- `evidence_claim`
- `enrichment_snapshot`
- `field_resolution`

### Scoring and recommendation

- `scoring_model`
- `scoring_model_version`
- `score_execution`
- `score_component`
- `score_override`
- `product`
- `product_match_rule`
- `product_recommendation`
- `weekly_shortlist`
- `weekly_shortlist_item`

### AI

- `ai_provider_configuration`
- `ai_task_execution`
- `prompt_template`
- `prompt_template_version`
- `ai_input_evidence`
- `ai_output`

No secret value may be stored in `ai_provider_configuration`.

### Outreach and communication

- `outreach_template`
- `outreach_draft`
- `outreach_draft_version`
- `approval_decision`
- `outbox_action`
- `communication`
- `communication_response`

### Compliance

- `contact_classification`
- `processing_basis_record`
- `suppression_record`
- `retention_review`
- `deletion_event`

### Operations

- `job_definition`
- `job_execution`
- `job_checkpoint`
- `integration_account`
- `api_usage_event`
- `audit_event`
- `backup_manifest`

The exact table structure may be adjusted for implementation quality, but the conceptual separation must remain.

## 8.3 Canonical values versus observations

Never overwrite a canonical lead field merely because a provider returns a new value.

Store source-derived values as observations.

Resolve canonical values through:

- deterministic source precedence;
- freshness rules;
- confidence;
- user confirmation;
- explicit `field_resolution` records.

Example:

- Google reports one address.
- Website structured data reports another.
- User confirms the active trading address.

All observations must remain traceable. The confirmed canonical field must point to its resolution source.

## 8.4 Evidence classification

Every material fact must support a classification such as:

- verified;
- user verified;
- user observed;
- provider observed;
- inferred;
- suggested;
- unknown.

Do not present inferred or suggested information as verified fact.

## 8.5 Identity resolution

Implement deterministic identity matching.

Indicative confidence rules:

- same provider and same provider ID: definitive within that provider;
- exact registrable website domain: very high confidence;
- exact normalised email or telephone: very high confidence;
- exact social handle: high confidence;
- normalised name plus postcode: high confidence;
- fuzzy name plus geographic proximity: possible match only;
- fuzzy name alone: never auto-merge.

Merges must preserve:

- source evidence;
- communication history;
- notes;
- scores;
- pipeline history;
- suppression state;
- audit history.

A suppressed record must remain suppressed after import or merge.

---

# 9. Security Requirements

## 9.1 Input validation

Validate and normalise all:

- user inputs;
- CSV data;
- provider responses;
- AI outputs;
- URLs;
- imported files;
- identifiers;
- dates;
- numeric values;
- HTML-derived content.

Reject malformed data with actionable errors.

## 9.2 Output safety

Never render raw external HTML.

Escape or sanitise all externally sourced text before rendering.

Protect against stored and reflected XSS.

## 9.3 SSRF controls

Before fetching a website URL:

- allow only `http` and `https`;
- reject embedded credentials;
- resolve DNS and reject loopback, link-local, private, multicast, reserved, and metadata-service ranges;
- repeat validation after every redirect;
- cap redirect depth;
- enforce request timeout;
- enforce response-size limit;
- enforce content-type allowlist;
- prevent access to local files and internal services;
- use a controlled user agent;
- avoid browser session cookies or credentials;
- block cross-domain crawling beyond explicitly allowed transitions.

Test IPv4, IPv6, DNS rebinding-style cases, encoded hosts, alternate numeric IP formats, and redirect bypasses.

## 9.4 CSV safety

Protect import and export from:

- malformed rows;
- oversized files;
- encoding errors;
- duplicate headers;
- type confusion;
- spreadsheet formula injection.

On export, neutralise cells beginning with:

```text
= + - @
```

where they could be interpreted as spreadsheet formulas.

## 9.5 Secret storage

Use Windows Credential Manager or DPAPI-backed protection.

The database may store:

- secret reference;
- provider name;
- account display metadata;
- scopes;
- token expiry metadata;
- status.

The database must not store raw secrets.

## 9.6 Logging and privacy

Logs must be structured and redacted.

Never log:

- API keys;
- OAuth tokens;
- passwords;
- full sensitive headers;
- complete provider payloads by default;
- unnecessary personal data;
- full outreach message content unless explicitly required and protected.

Use correlation IDs across API requests, jobs, and integration calls.

## 9.7 Dependency security

Use pinned dependencies and lockfiles.

Add automated dependency vulnerability scanning where practical.

Do not introduce unmaintained packages for convenience.

Record any high-risk dependency acceptance in an ADR.

---

# 10. Compliance and Suppression Controls

This implementation must include product controls that support UK privacy and marketing compliance. These controls do not replace professional legal advice.

## 10.1 Contact classification

Every lead/contact route must support classification as:

- corporate subscriber;
- sole trader or individual subscriber;
- partnership requiring individual treatment;
- unknown.

Unknown classification must create a visible warning.

It must block any future unattended send and require deliberate review before outreach preparation or approval according to configured policy.

## 10.2 Mandatory outreach checks

Before approving or recording outreach, validate:

- lead is not suppressed;
- contact route is active;
- sender identity is configured;
- opt-out method or approved wording is available;
- contact classification has been reviewed or visibly acknowledged;
- source and collection date exist;
- no recent conflicting communication exists;
- no duplicate associated record is suppressed or recently contacted;
- proposed offer is approved;
- no unsupported claim exists.

## 10.3 Suppression invariant

A Do Not Contact, objection, or unsubscribe state must override:

- weekly shortlist inclusion;
- outreach generation queues;
- approval;
- future send actions;
- imports;
- merges;
- campaign recommendations.

Suppression checks must occur at query time and again transactionally at approval/send time.

## 10.4 Deletion and minimal suppression retention

Lead deletion must remove unnecessary prospect and personal data.

Where justified, retain a minimal suppression fingerprint sufficient to prevent re-contact, such as normalised or hashed contact identifiers plus:

- suppression reason;
- date;
- source;
- limited audit metadata.

Do not retain a full deleted lead profile solely for suppression.

## 10.5 Legal-review feature gate

Automated external sending must remain disabled until a separate legal, privacy, technical, and operational review is recorded.

---

# 11. Discovery and Enrichment Implementation

## 11.1 Source-adapter interface

Each discovery adapter should implement an application-owned contract equivalent to:

```text
validate_configuration()
estimate(request) -> count, cost, warnings
discover(request, cursor) -> CandidateBatch
fetch_details(external_id) -> SourceObservationBatch
health_check() -> IntegrationHealth
```

The adapter must return provider-neutral domain objects.

Each candidate should include:

- source system;
- external ID;
- source URL;
- observed display name;
- observed location;
- observed type/category;
- retrieval timestamp;
- raw-response hash;
- provider-policy or caching classification;
- confidence;
- adapter version.

## 11.2 Manual lead entry

Implement first-class manual entry with:

- validation;
- source attribution;
- duplicate warning;
- contact classification;
- explicit verification classification;
- audit event.

Manual workflows must remain usable if every external provider is disabled.

## 11.3 CSV import

Use a staged import workflow:

1. Upload and parse.
2. Preview rows.
3. Map columns.
4. Validate.
5. Show invalid rows.
6. Detect duplicates.
7. Allow row-level include/exclude decisions.
8. Confirm import.
9. Execute transactionally in batches.
10. Present created, merged, skipped, and failed counts.

Do not create records before user confirmation.

## 11.4 Google discovery

Implement only through an approved API/provider adapter.

MVP pattern:

1. Use minimal search fields to discover candidates.
2. Show estimated provider usage/cost before execution.
3. Limit candidate count and request count.
4. Fetch detail fields only for shortlisted or explicitly selected candidates.
5. Store provider IDs and policy metadata.
6. Keep provider observations separate from canonical lead facts.
7. Display required attribution where applicable.
8. Provide assisted-search/manual-capture fallback.

Never use wildcard field selection in production.

Never design the local database as an unrestricted permanent mirror of provider data.

## 11.5 Instagram and Facebook

MVP functionality is limited to:

- prepared search links;
- open profile in external browser;
- manual profile URL and handle capture;
- user-observed follower range;
- user-observed activity/posting information;
- source/date classification;
- copy DM text;
- manual sent confirmation.

Do not implement automated discovery or extraction without a separately approved architecture spike and official API basis.

## 11.6 Website enrichment

Website enrichment must:

- start from an explicitly supplied public business domain;
- prefer structured data and clearly public contact pages;
- limit depth and pages;
- restrict crawling to the same registrable domain unless a user approves a link;
- use per-domain rate limits;
- respect configured robots and policy rules;
- retain source URLs and timestamps;
- classify extraction confidence;
- allow partial success;
- provide manual fallback;
- never block core lead management after failure.

Recommended initial pages:

- homepage;
- contact;
- about;
- services/products;
- menu or portfolio where directly relevant.

Do not download large media files in the MVP.

---

# 12. Lead Scoring and Qualification

## 12.1 Bakery model

Implement the first production scoring model for bakeries and home-baking businesses.

Default weighted categories:

- Business relevance: 25.
- Activity: 20.
- Product fit: 20.
- Local relevance: 15.
- Commercial potential: 10.
- Reach and credibility: 5.
- Contactability: 5.

Total: 100.

Each scoring criterion must reference explicit evidence IDs or an explicit missing-data state.

## 12.2 Score execution record

Store:

- scoring model ID;
- scoring model version;
- lead ID;
- campaign ID;
- total score;
- category scores;
- criterion outcomes;
- evidence IDs;
- missing evidence;
- execution timestamp;
- calculation code/version;
- manual override;
- override reason;
- actor.

## 12.3 Manual override

Allow score override only with a recorded reason.

Never discard the original calculated score.

Display calculated and overridden values distinctly.

## 12.4 Segment extensibility

Architect the rule engine for future segment models without hardcoding bakery-specific logic into UI components or database columns.

Only the bakery model needs full production validation in the MVP.

Other segments may use generic or draft configurations but must be clearly labelled as not yet calibrated.

---

# 13. Product Matching

Implement an editable local product catalogue.

Minimum fields:

- product ID;
- name;
- category;
- description;
- target segments;
- use cases;
- active status;
- image reference;
- optional pricing guidance;
- sample eligibility;
- source/version metadata.

Product matching must support:

1. deterministic segment/product rules;
2. evidence-based rule outcomes;
3. optional AI-assisted recommendations;
4. explanation of why each product fits;
5. user reorder, add, remove, and edit;
6. approved-offer controls.

No product recommendation may automatically promise price, discount, lead time, availability, or sample.

---

# 14. Weekly Shortlist

Generate a controlled weekly shortlist using:

- lead score;
- product fit;
- local relevance;
- contactability;
- evidence freshness;
- previous contact history;
- suppression status;
- campaign state;
- pipeline stage;
- configured weekly capacity.

Default target: 5–10 leads.

The shortlist must exclude:

- suppressed leads;
- recently contacted leads unless follow-up is due;
- unqualified leads;
- inactive campaigns;
- unresolved high-confidence duplicates;
- leads whose required compliance checks block outreach.

Each item must display a human-readable selection reason.

Users must be able to defer, dismiss, or replace a recommendation.

The shortlist generation must be reproducible for the same inputs and model version.

---

# 15. AI Gateway and AI Tasks

## 15.1 Provider abstraction

Implement one provider initially behind an application-owned interface supporting:

- structured completion;
- timeout and cancellation;
- usage extraction;
- provider error classification;
- model capability metadata;
- retry-safe invocation where appropriate.

Do not expose provider SDK types outside the adapter.

## 15.2 Allowed MVP tasks

AI may perform:

- business summary;
- evidence categorisation suggestions;
- product-fit narrative;
- outreach-angle recommendation;
- email drafting;
- Instagram DM drafting;
- deterministic score explanation;
- lead-note summarisation.

## 15.3 Execution pattern

Every AI execution must:

1. Build a minimised evidence packet.
2. Include evidence IDs and classifications.
3. Use a versioned prompt template.
4. Request structured JSON.
5. Validate output with Pydantic/JSON Schema.
6. Reject unknown evidence IDs.
7. reject prohibited claims or mark for review;
8. record provider, model, prompt version, input hash, token usage, latency, status, and error class;
9. cache by task type, prompt version, model profile, and canonical input hash;
10. display output as advisory content requiring human review.

## 15.4 AI cost controls

Implement:

- per-task model selection;
- per-run limit;
- campaign budget;
- monthly provider budget;
- request/token logging;
- cached-result reuse;
- stale-input detection;
- confirmation for unusually large operations;
- visible estimated versus actual usage.

## 15.5 Safe failure

If AI is unavailable, the user must still be able to:

- create/edit leads;
- score leads deterministically;
- manage pipeline;
- write outreach manually;
- approve or reject content;
- use follow-ups;
- export and back up data.

---

# 16. Outreach, Approval, and Communication Controls

## 16.1 Draft versioning

Every draft must have immutable versions.

Store:

- draft ID;
- version;
- channel;
- subject where applicable;
- content;
- product proposition;
- call to action;
- evidence references;
- template version;
- AI execution reference where applicable;
- content hash;
- status;
- created/edited timestamps;
- actor.

## 16.2 Approval invariant

Approval must refer to a specific draft version and content hash.

Editing a draft must:

- create a new version;
- invalidate existing approval;
- return status to edited/unapproved;
- create an audit event.

At approval time validate transactionally:

- draft version and hash are current;
- lead is not suppressed;
- duplicate-contact warning is resolved;
- contact route still matches;
- contact classification has been handled;
- offers are approved;
- evidence-based personalisation contains no unsupported claims;
- no conflicting in-flight action exists.

## 16.3 MVP email workflow

The MVP must:

- generate subject/body;
- allow editing;
- approve a specific version;
- copy subject and body;
- optionally open Zoho Mail in browser/app where practical;
- require the user to confirm whether the message was sent;
- record manual-send timestamp and confirmation;
- create a follow-up when appropriate.

Do not mark an email sent merely because the content was copied.

## 16.4 MVP Instagram workflow

The MVP must:

- generate concise DM text;
- allow editing and approval;
- copy the approved version;
- open the stored Instagram profile externally;
- require manual sent confirmation;
- record the communication and follow-up.

## 16.5 Zoho phase gate

Do not implement direct sending in the MVP.

Phase 2 order:

1. OAuth technical spike.
2. Integration account setup and secure token storage.
3. Create Zoho draft only.
4. Reconcile draft IDs/status.
5. Production review.
6. Only then consider approved direct send with idempotency and uncertain-send reconciliation.

---

# 17. Pipeline and Follow-Up Design

Store detailed pipeline stages from the BRD/FSD, but group them in the default UI as:

1. New / Researching.
2. Qualified / Recommended.
3. Ready / Contacted / Follow-Up.
4. Replied / Mock-Up / Sample.
5. Quote / Negotiating.
6. Won / Lost / Not Suitable / Do Not Contact.

Every stage change must create an append-only stage event with:

- previous stage;
- new stage;
- timestamp;
- actor;
- reason where applicable.

Follow-ups must support:

- type;
- due date;
- status;
- notes;
- completion date;
- creation of next action;
- due today;
- overdue;
- due this week.

No unattended multi-step sequence is permitted.

---

# 18. Persistent Jobs and Recovery

## 18.1 Job states

Use explicit states such as:

```text
queued
running
waiting_retry
succeeded
partially_succeeded
failed
cancelled
requires_reconciliation
```

## 18.2 Startup recovery

On application/worker startup:

- find running jobs with expired leases;
- safely return idempotent jobs to queue or retry state;
- retain checkpoints;
- mark non-idempotent uncertain actions for manual reconciliation;
- never infer an external send failed solely because the response was lost;
- report recovered/blocked jobs in diagnostics.

## 18.3 Retry policy

Retry only:

- transient network errors;
- rate limits;
- selected 5xx errors;
- explicitly classified provider transient failures.

Use exponential backoff with jitter and honour `Retry-After`.

Do not automatically retry:

- invalid input;
- authentication errors;
- policy violations;
- unsupported operations;
- permanent 4xx failures;
- suppressed outreach;
- rejected AI schema output without correction.

## 18.4 Windows scheduling

Persist schedules in SQLite.

The application schedule is the source of truth.

Where scheduled work must run while the UI is closed, optionally use Windows Task Scheduler only as a wake-up mechanism to execute a limited `run-due-jobs` command.

Do not make Windows Task Scheduler the business-state store.

---

# 19. Backup, Restore, and Data Portability

Implement:

- manual backup;
- optional scheduled daily backup;
- SQLite-consistent backup;
- backup manifest;
- checksum/integrity validation;
- database integrity check;
- restore preview;
- restore confirmation;
- restore into a test location before replacement where practical;
- encrypted-backup option;
- configurable backup location;
- retention policy;
- export to CSV and JSON.

Target objectives:

- **RPO:** no more than 24 hours where scheduled backup is enabled; zero relative to a successful manual backup.
- **RTO:** restore within 30 minutes for data at stated MVP scale.

A release cannot be declared pilot-ready until backup and restore have been demonstrated end to end.

---

# 20. Observability and Diagnostics

Implement:

- structured application logs;
- rotating log files;
- correlation IDs;
- provider health status;
- database health status;
- migration version;
- job queue status;
- failed-job summary;
- discovery run summary;
- API usage summary;
- backup status;
- diagnostics export with secret redaction;
- local health endpoint accessible only through loopback/session controls.

The UI should present actionable errors, not raw stack traces.

Retain full technical detail in local logs while protecting sensitive data.

---

# 21. Frontend and UX Requirements

The interface must remain simple enough for a single small-business owner without CRM training.

Primary navigation:

1. Dashboard.
2. Weekly Leads.
3. All Leads.
4. Campaigns.
5. Pipeline.
6. Outreach.
7. Analytics.
8. Settings.

## 21.1 Core UX rules

- Keep the weekly workflow prominent.
- Display a clear next action for each lead.
- Distinguish verified fact, observation, inference, and suggestion visually.
- Show source and freshness where relevant.
- Never hide suppression or compliance warnings.
- Avoid overwhelming the user with all detailed pipeline states.
- Support keyboard navigation.
- Use accessible labels, focus states, contrast, and error messaging.
- Preserve draft changes.
- Confirm destructive actions.
- Use optimistic UI only where rollback is safe.
- Prevent double submission.
- Show background job progress and partial-result states.

## 21.2 Required operational dashboard panels

- recommended leads this week;
- follow-ups due;
- approved but unsent emails;
- Instagram DMs ready to copy;
- recent replies;
- quote requests;
- pipeline summary;
- data-quality warnings;
- suppression/compliance warnings;
- integration health;
- failed or blocked jobs.

## 21.3 Accessibility target

Aim for practical WCAG 2.2 AA alignment for core workflows.

At minimum test:

- keyboard-only usage;
- visible focus;
- form labels;
- validation messages;
- sufficient contrast;
- screen-reader semantics for tables, cards, dialogs, and status changes;
- reduced motion where applicable.

---

# 22. API and Error-Handling Standards

Use explicit typed request/response contracts.

Adopt a consistent error shape such as:

```json
{
  "code": "LEAD_DUPLICATE_REVIEW_REQUIRED",
  "message": "A possible duplicate requires review before this lead is created.",
  "details": {},
  "correlation_id": "..."
}
```

Rules:

- no raw provider errors returned directly to UI;
- classify validation, conflict, authentication, authorisation, rate-limit, transient-provider, permanent-provider, and internal errors;
- preserve correlation IDs;
- use appropriate HTTP status codes;
- make user-facing messages actionable;
- avoid leaking sensitive configuration;
- include retry guidance only when appropriate.

---

# 23. Testing Requirements

Testing is part of implementation, not a later activity.

## 23.1 Unit and domain tests

Cover:

- scoring rules;
- score versioning;
- manual overrides;
- duplicate-confidence calculation;
- identity normalisation;
- field resolution;
- suppression checks;
- approval invalidation;
- shortlist inclusion/exclusion;
- product matching;
- contact classification warnings;
- retention calculations;
- job-state transitions;
- retry classification;
- cost-budget logic.

## 23.2 Database tests

Cover:

- migrations from clean database;
- migrations from prior versions;
- foreign keys;
- unique constraints;
- merge transactions;
- suppression preservation;
- WAL behaviour;
- concurrent read/write scenarios;
- backup consistency;
- restore verification;
- integrity checks;
- FTS indexes where used.

## 23.3 Adapter contract tests

Every external adapter must pass common tests for:

- configuration validation;
- health check;
- estimate output;
- pagination/cursors;
- timeout;
- rate limit;
- transient failure;
- permanent failure;
- partial results;
- redaction;
- provider-neutral mapping;
- idempotency.

Use mocked or recorded fixtures without exposing real secrets.

## 23.4 Security tests

Cover:

- loopback-only binding;
- invalid session token;
- XSS payloads in imported/provider content;
- SSRF bypass attempts;
- unsafe redirects;
- private and metadata IP ranges;
- CSV formula injection;
- oversized imports/responses;
- secret redaction;
- path traversal;
- malicious filenames;
- draft approval hash mismatch;
- suppressed lead at approval time;
- suppressed lead during merge/import;
- OAuth state/PKCE when introduced.

## 23.5 AI tests

Create a bakery-focused golden dataset containing at least 30 representative prospects, including:

- strong fit;
- weak fit;
- inactive business;
- duplicate;
- missing data;
- ambiguous sole trader;
- wedding-focused bakery;
- high follower count but poor product relevance;
- strong repeat-order potential;
- evidence conflicts;
- prohibited personalisation traps.

Evaluate:

- factuality;
- evidence references;
- unsupported claims;
- product-fit usefulness;
- message tone;
- schema validity;
- prohibited statements;
- user edit distance.

## 23.6 End-to-end tests

Automate the critical pilot journey:

1. Start application.
2. Create campaign.
3. Add/import lead.
4. Review duplicate warning.
5. add evidence.
6. calculate score.
7. generate weekly shortlist.
8. create AI summary/draft using mock adapter.
9. edit draft.
10. verify approval invalidation.
11. approve current version.
12. copy and manually confirm sent.
13. create follow-up.
14. record reply and outcome.
15. suppress lead and verify exclusion.
16. export data.
17. back up.
18. restore and verify.

## 23.7 Regression requirement

Every defect fix must include a regression test unless technically impossible. If impossible, document the reason and add an alternative verification step.

---

# 24. Performance and Scale Targets

Validate against at least:

- 10,000 leads;
- 100 campaigns;
- 50,000 evidence records;
- 100,000 activity/audit records;
- CSV import of 1,000 leads;
- practical weekly job workloads.

Indicative targets:

- dashboard initial load within 3 seconds under normal local use;
- lead search within 2 seconds at target scale;
- lead detail within 2 seconds excluding external refresh;
- no application failure during 1,000-row import;
- long-running external tasks executed asynchronously through durable jobs;
- UI remains responsive during background operations.

Record benchmark methodology and results.

Do not optimise prematurely, but add required indexes and eliminate obvious N+1 queries.

---

# 25. Delivery Stages

Implement incrementally. Each stage must be usable, tested, documented, and reviewed before moving to the next.

## Stage 0 — Architecture and risk spikes

Deliver thin technical proofs for:

- Tauri sidecar/backend process management;
- loopback/session security;
- SQLite WAL and migrations;
- consistent backup/restore;
- Google provider field/cost pattern using a restricted test setup or mock where credentials are unavailable;
- website fetcher SSRF controls;
- one AI structured-output task;
- Windows credential storage;
- Windows packaging feasibility.

### Stage 0 exit criteria

- high-risk assumptions demonstrated;
- ADRs recorded;
- no unresolved release-blocking architecture uncertainty;
- fallback documented for any unsuccessful spike.

## Stage 1 — Local operating core

Implement:

- desktop shell;
- local API;
- database and migrations;
- campaign CRUD;
- manual lead entry;
- CSV staged import;
- lead list/detail;
- pipeline;
- notes;
- follow-ups;
- suppression;
- audit events;
- export;
- backup/restore;
- basic settings and diagnostics.

### Stage 1 outcome

A useful lightweight local CRM must work without any external API.

### Stage 1 release gate

- no critical/high security defect;
- migration tests pass;
- backup/restore demonstrated;
- suppressed leads cannot enter outreach-ready states;
- core E2E tests pass.

## Stage 2 — Evidence and qualification

Implement:

- source systems;
- observations and evidence claims;
- canonical-field resolution;
- identity resolution and merge review;
- deterministic bakery scoring;
- scoring explanations;
- product catalogue;
- deterministic product matching;
- weekly shortlist.

### Stage 2 outcome

The user can rank and prioritise manually entered/imported bakery prospects using transparent evidence.

### Stage 2 release gate

- score always traces to evidence/missing state;
- fuzzy name alone never auto-merges;
- suppression survives merge;
- shortlist excludes invalid leads;
- scoring golden tests pass.

## Stage 3 — Controlled discovery

Implement:

- source-adapter framework;
- pre-run estimates and budgets;
- persistent worker and job recovery;
- approved Google discovery adapter or mockable equivalent;
- assisted Instagram/Facebook capture;
- safe website enrichment;
- partial-result handling;
- provider health/status.

### Stage 3 outcome

The user can build a practical pilot database without unauthorised scraping.

### Stage 3 release gate

- website fetcher passes SSRF tests;
- job recovery is demonstrated after forced shutdown;
- provider limits and cost controls are visible;
- external failures do not corrupt existing lead data;
- manual fallback works.

## Stage 4 — AI and controlled outreach

Implement:

- AI gateway;
- prompt and model versioning;
- evidence packets;
- structured-output validation;
- business summaries;
- product-fit narratives;
- email drafts;
- Instagram DM drafts;
- tone/templates;
- immutable draft versions;
- approval/content hash;
- copy/open/manual-send confirmation;
- communication timeline.

### Stage 4 outcome

The full manual-approval MVP workflow operates end to end.

### Stage 4 release gate

- editing invalidates approval;
- suppressed leads cannot be approved;
- AI output with unknown evidence IDs is rejected;
- no email or DM is sent automatically;
- AI provider failure leaves manual workflow usable;
- end-to-end pilot flow passes.

## Stage 5 — Pilot hardening

Implement and complete:

- analytics;
- performance testing;
- security review;
- accessibility review;
- installer and clean-machine test;
- diagnostics;
- operational runbook;
- legal/compliance action register;
- pilot data seed/template;
- 4–6 week pilot support instrumentation.

### Stage 5 outcome

A pilot-ready Windows application for the Luton bakery campaign.

### Pilot gate

Do not begin production outreach until:

- backup/restore is proven;
- compliance warnings and suppression work;
- legal/privacy review actions are acknowledged;
- provider configuration and budgets are approved;
- end-to-end tests pass;
- installer works on a clean Windows profile;
- no unresolved critical/high defect remains.

---

# 26. Explicitly Deferred Features

Do not implement these during the MVP unless the business owner explicitly changes scope:

- automated Instagram discovery;
- automated Facebook discovery;
- Instagram/Facebook login automation;
- automated DMs;
- direct Zoho sending;
- unattended email sequences;
- Shopify catalogue sync;
- multi-user access;
- enterprise RBAC;
- UK-wide scaling optimisation;
- local AI models;
- learning-based scoring;
- mobile companion app;
- integrated quote builder;
- full revenue attribution;
- referral campaigns;
- autonomous price or discount decisions.

Prepare clean extension points, but do not build speculative infrastructure for deferred features.

---

# 27. Documentation Deliverables

Maintain the following documentation during implementation:

```text
docs/implementation/BASELINE_ASSESSMENT.md
docs/implementation/IMPLEMENTATION_PLAN.md
docs/implementation/REQUIREMENTS_TRACEABILITY.md
docs/implementation/DELIVERY_LOG.md
docs/architecture/SYSTEM_CONTEXT.md
docs/architecture/COMPONENT_DESIGN.md
docs/architecture/DATA_MODEL.md
docs/architecture/SECURITY_MODEL.md
docs/architecture/JOB_DESIGN.md
docs/architecture/INTEGRATION_ADAPTERS.md
docs/operations/LOCAL_SETUP.md
docs/operations/BUILD_AND_PACKAGE.md
docs/operations/BACKUP_AND_RESTORE.md
docs/operations/TROUBLESHOOTING.md
docs/testing/TEST_STRATEGY.md
docs/testing/PILOT_ACCEPTANCE_REPORT.md
docs/compliance/CONTROL_REGISTER.md
docs/adr/ADR-*.md
```

Update documentation in the same change as the related code.

---

# 28. Architecture Decision Records

Create ADRs at minimum for:

1. Desktop wrapper selection.
2. Modular monolith architecture.
3. Frontend stack.
4. Backend stack.
5. SQLite WAL persistence.
6. Persistent job mechanism.
7. Windows secret storage.
8. Google/provider data handling.
9. Assisted Instagram/Facebook workflow.
10. Deterministic scoring.
11. Canonical versus observed data.
12. AI advisory model and structured validation.
13. Zoho draft-before-send strategy.
14. Backup and restore strategy.
15. Loopback and session security.

Each ADR must include:

- status;
- context;
- decision;
- alternatives considered;
- consequences;
- security/compliance impact;
- rollback or migration consideration.

---

# 29. Definition of Done

A feature is complete only when:

- requirement and acceptance criteria are identified;
- implementation follows architecture boundaries;
- input and output validation exist;
- security and compliance controls are applied;
- unit tests pass;
- integration/contract tests pass where applicable;
- regression tests exist;
- UI handles loading, empty, success, partial, and error states;
- audit/logging is appropriate;
- migration is included where required;
- documentation is updated;
- no secret is committed;
- linting, formatting, and type checks pass;
- accessibility has been considered;
- manual acceptance steps are documented;
- change is recorded in the delivery log.

“Code compiles” is not a sufficient definition of done.

---

# 30. Mandatory Quality Gates

Before declaring any stage complete, run and report:

- frontend lint;
- frontend type check;
- frontend unit tests;
- backend lint;
- backend type check;
- backend unit tests;
- migration tests;
- integration tests;
- security tests relevant to the stage;
- end-to-end tests relevant to the stage;
- production build;
- Windows packaging smoke test where available.

Provide exact commands and results.

Do not hide failing tests, disable checks, or reduce assertions to obtain a passing build.

A quarantined test requires a documented defect, owner, and removal condition.

---

# 31. Change-Control Rules

Before each material implementation increment:

1. State the scope.
2. Identify affected requirements.
3. Identify affected modules and migrations.
4. Identify data-loss, security, compliance, and regression risks.
5. Define tests and rollback.
6. Implement the smallest coherent increment.
7. Run quality gates.
8. Update documentation and delivery log.

Do not perform broad unrelated refactors in the same change.

Do not change business behaviour without documenting the requirement or ADR basis.

Do not alter functioning external integrations without contract tests.

---

# 32. Coding Standards

Apply the following:

- strict typing;
- small focused functions;
- explicit domain names;
- no magic values for business rules;
- configuration schemas with defaults and validation;
- immutable DTOs where practical;
- explicit transaction boundaries;
- dependency injection for adapters and services;
- no hidden global mutable state;
- UTC storage for timestamps and local display conversion;
- stable IDs using UUIDs or equivalent;
- safe decimal handling for currency;
- registrable-domain parsing through a maintained library;
- normalisation utilities covered by tests;
- comments explain why, not obvious syntax;
- avoid premature abstraction;
- avoid copy-pasted provider logic;
- keep UI components focused;
- use semantic HTML;
- make destructive actions explicit and reversible where practical.

---

# 33. Initial Seed Configuration

Provide optional seed/demo data for development and testing only.

Initial production configuration should support:

- campaign name: `Luton Bakery Partnerships`;
- segment: bakeries and home-baking businesses;
- centre: Luton, United Kingdom;
- radius: 25 miles;
- weekly shortlist: 5–10;
- primary products: cake toppers, cake charms, bakery branding accessories;
- channels: email and Instagram;
- default offer suggestions: free digital mock-up and introductory pricing;
- physical sample: only after positive reply and explicit approval.

Do not automatically create or contact real leads during development.

Use synthetic data in tests and demos.

---

# 34. Required Initial Implementation Plan Output

After completing repository assessment and before substantial coding, produce:

```text
docs/implementation/IMPLEMENTATION_PLAN.md
```

It must include:

1. Current-state summary.
2. Confirmed target architecture.
3. Repository changes required.
4. Stage-by-stage backlog.
5. Requirement traceability.
6. Data-model implementation plan.
7. Migration plan.
8. Security plan.
9. Compliance-control plan.
10. Integration-adapter plan.
11. AI plan.
12. Testing plan.
13. Windows packaging plan.
14. Risks and mitigations.
15. Dependencies and credentials required.
16. Explicit deferred scope.
17. Proposed first coding increment.

Do not wait for approval where the implementation direction is already unambiguous. Begin Stage 0 and Stage 1 work after recording the plan, while flagging only genuine blockers.

---

# 35. Required Progress Reporting

At the end of each implementation increment, report:

- completed work;
- files changed;
- migrations created;
- tests added;
- tests run and result;
- security/compliance controls added;
- known limitations;
- requirement traceability updates;
- next recommended increment.

Be explicit about partial completion and failures.

Do not claim a feature works unless it has been executed or tested.

---

# 36. Stop Conditions

Stop and clearly report rather than proceeding unsafely when:

- a requested change requires unauthorised scraping or bypassing access controls;
- secrets are unavailable and no mock/fallback can be used;
- a migration risks data loss without a recoverable backup;
- a provider’s terms materially conflict with the proposed design;
- an external send cannot be made idempotent or reconciled;
- a security control cannot be implemented as required;
- the repository contains uncommitted user changes that would be overwritten;
- implementation would silently violate suppression or approval invariants.

Where possible, continue with safe local functionality, mocks, adapters, or documentation while isolating the blocker.

---

# 37. Final MVP Acceptance Criteria

The MVP is complete only when all of the following are demonstrated:

1. The user can install and start the app on Windows.
2. Backend services bind only to loopback.
3. The user can create the Luton bakery campaign.
4. The user can add leads manually.
5. The user can stage and import a CSV.
6. Duplicate candidates are detected and reviewed.
7. Source observations remain separate from canonical facts.
8. Evidence is classified and traceable.
9. Bakery scoring is deterministic, versioned, and explainable.
10. Product recommendations show evidence and method.
11. The app generates a weekly shortlist of 5–10 suitable leads.
12. Suppressed and recently contacted leads are correctly excluded.
13. Assisted Instagram/Facebook capture works without automation.
14. Website enrichment passes safety controls.
15. External jobs recover correctly after application interruption.
16. AI output is schema validated and evidence bound.
17. Email and Instagram drafts can be generated and edited.
18. Editing invalidates approval.
19. No external communication is sent automatically.
20. Manual sending requires confirmation.
21. Communication history and follow-ups are recorded.
22. Pipeline outcomes, mock-ups, samples, quotes, wins, and losses can be tracked.
23. Analytics show the pilot funnel and source/channel performance.
24. Secrets are protected using Windows-native storage.
25. Logs and diagnostics redact secrets.
26. Data can be exported.
27. A consistent backup can be created.
28. Backup integrity can be verified.
29. Data can be restored successfully.
30. Core E2E, security, migration, and regression tests pass.
31. Installer/build is tested on a clean Windows profile.
32. No unresolved critical or high-severity issue remains.

---

# 38. Start Implementation Now

Execute the work in this order:

1. Read all authoritative documents.
2. Inspect the complete repository.
3. Create the baseline assessment.
4. Create/update requirement traceability.
5. Confirm or amend the architecture through ADRs.
6. Create the implementation plan.
7. Run Stage 0 risk spikes.
8. Begin Stage 1 with the smallest end-to-end vertical slice.
9. Add tests and documentation with every increment.
10. Continue through the staged roadmap while enforcing all guardrails.

The first vertical slice should prove:

```text
Desktop starts
→ local API health succeeds
→ SQLite migration runs
→ campaign can be created
→ lead can be entered manually
→ source attribution is stored
→ lead appears in list/detail
→ audit event is recorded
→ application restarts without losing data
→ backup and restore smoke test succeeds
```

Do not start with Google, AI, Meta, Zoho, or advanced analytics before the local operating core and data-safety controls are working.

The expected result is a secure, explainable, maintainable **local lead-intelligence workbench** for Etch ’N’ Shine—not an autonomous prospecting bot.
