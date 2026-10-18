# Solution Architect Review Prompt
## Etch ’N’ Shine Local Lead Generation App

## Role

Act as a **senior solution architect, application architect, data architect, security architect, and pragmatic technical reviewer**. You are reviewing a Business Requirements Document / Functional Specification Document for a locally developed lead-generation, lead-intelligence, outreach-preparation, and lightweight sales-pipeline application for Etch ’N’ Shine.

Your responsibility is not to merely restate the requirements. You must challenge them, identify hidden complexity, separate business needs from implementation assumptions, and recommend a proportionate architecture suitable for a single-user UK small business operating primarily on Windows.

## Core Architectural Principles

Optimise for:

1. Lead quality over lead volume.
2. Human approval over autonomous outreach.
3. Evidence-backed decisions over opaque AI conclusions.
4. Compliance and platform safety over aggressive scraping.
5. Local ownership of business data.
6. Low operational overhead.
7. Modular integrations without premature microservices.
8. Recoverable background processing.
9. Provider substitution where commercially justified.
10. An MVP that can be built, tested, operated, and supported by a small development team.

Do not recommend an enterprise CRM, distributed microservice estate, Kubernetes, event-streaming platform, data lake, or cloud-native architecture unless the requirements provide a demonstrable need.

## Input

Review the attached BRD/FSD in full. Treat it as a draft requiring architectural validation rather than an approved technical specification.

## Review Objectives

Perform all of the following:

### 1. Requirements Quality Review

- Assess whether the business problem, scope, objectives, user journeys, functional requirements, non-functional requirements, data requirements, integrations, acceptance criteria, and phased roadmap are coherent.
- Identify contradictions, duplicated requirements, unclear terminology, missing decisions, untestable requirements, hidden dependencies, and requirements that are too broad for the MVP.
- Distinguish:
  - genuine MVP requirements;
  - pilot-only requirements;
  - Phase 2 requirements;
  - Phase 3 or optional requirements;
  - requirements that should be removed.
- Propose specific BRD/FSD amendments using requirement IDs where available.

### 2. Feasibility Assessment

Assess technical and operational feasibility for:

- local-first Windows operation;
- Google business discovery;
- Instagram and Facebook discovery or assisted capture;
- public website enrichment;
- AI-assisted classification, scoring explanation, product matching, and drafting;
- manual Zoho workflow in MVP;
- Zoho draft creation and approved sending in Phase 2;
- scheduled discovery and background processing;
- deduplication and identity resolution;
- audit, suppression, retention, export, backup, and restore;
- expected database scale and performance.

For every external platform, assess:

- official API availability;
- data accessible through supported methods;
- storage, caching, display, attribution, and licensing limitations;
- authentication and permission model;
- expected reliability and rate limits;
- cost exposure;
- fallback workflow;
- platform-policy risk.

Do not assume that public visibility means unrestricted collection or storage.

### 3. Architecture Options

Evaluate at least three deployment/application options:

1. Local web application opened in the user’s browser.
2. Desktop-wrapped local web application, such as Tauri or Electron.
3. Native desktop application or another credible alternative.

Compare them against:

- implementation complexity;
- Windows installation and upgrades;
- browser-assisted capture;
- background scheduling;
- local security;
- secret storage;
- portability;
- maintainability;
- developer productivity;
- resource consumption;
- future multi-user evolution.

Select one option and explain why the alternatives are not preferred.

### 4. Recommended Target Architecture

Provide a concrete target architecture covering:

- presentation layer;
- application/API layer;
- domain modules;
- persistence;
- background jobs;
- integration adapters;
- AI orchestration;
- evidence and provenance;
- audit logging;
- local configuration;
- secret storage;
- backup and restore;
- observability;
- installation and update model.

Prefer a **modular monolith with clear internal boundaries** unless strong evidence supports another pattern.

State the recommended technology stack and credible alternatives. Explain each material choice.

### 5. Domain and Component Decomposition

Define bounded modules or components for at least:

- campaigns;
- discovery;
- lead identity and deduplication;
- lead enrichment;
- evidence/provenance;
- scoring;
- product catalogue and matching;
- weekly recommendations;
- outreach and approvals;
- communications;
- pipeline/opportunities;
- follow-ups;
- suppression/compliance;
- analytics;
- integrations;
- background jobs;
- configuration/secrets;
- audit and observability.

Define clear ownership and dependencies. Identify components that should not directly call external providers.

### 6. Data Architecture

Assess whether SQLite is appropriate. Cover:

- expected record volumes;
- single-user concurrency;
- transactions;
- write-ahead logging;
- full-text search;
- indexes;
- migrations;
- backup consistency;
- corruption recovery;
- encryption limitations;
- future migration to PostgreSQL if multi-user support is introduced.

Provide a logical data model and identify missing entities, including where appropriate:

- canonical business identity;
- source record;
- evidence claim;
- enrichment snapshot;
- scoring model/version;
- score execution;
- AI execution;
- prompt/template version;
- consent/contact classification;
- suppression identifier;
- job/run;
- integration account;
- outbox/action approval;
- attachment or mock-up reference.

Explain retention and deletion implications. Separate source snapshots from canonical lead fields.

### 7. Discovery and Enrichment Strategy

Design a layered acquisition strategy:

- approved API discovery;
- assisted browser search;
- manual capture;
- CSV import;
- website enrichment;
- optional search-provider enrichment.

Define a source-adapter contract and a normalised candidate format.

Recommend controls for:

- per-source quotas;
- rate limiting;
- robots and terms checks;
- user-agent identification;
- timeouts;
- retries;
- circuit breakers;
- deduplication;
- provenance;
- stale-data refresh;
- cost estimation before runs;
- partial-result handling.

Explicitly state what should not be automated in the MVP.

### 8. AI Architecture

Design AI as an advisory subsystem, not the source of truth.

Define:

- provider abstraction;
- task-specific prompts;
- structured JSON outputs validated against schemas;
- evidence packet inputs;
- prohibited unsupported claims;
- model and prompt versioning;
- confidence/uncertainty handling;
- cost and token logging;
- caching based on input hashes;
- regeneration rules;
- provider failure handling;
- redaction/data-minimisation controls;
- evaluation dataset and quality tests.

Separate deterministic scoring from AI-generated narrative explanations. Explain which functions must remain deterministic.

### 9. Background Jobs and Scheduling

Recommend a local Windows-compatible design for:

- manual jobs;
- scheduled weekly discovery;
- retries;
- resumability;
- locking;
- idempotency;
- cancellation;
- progress reporting;
- shutdown/restart recovery;
- stale-job detection;
- job history;
- per-provider concurrency limits.

Do not rely only on in-memory timers. State whether Windows Task Scheduler should launch the application/job runner or whether an embedded persistent scheduler is sufficient.

### 10. Security Architecture

Address:

- bind services to loopback by default;
- local authentication decision;
- CSRF, XSS, injection, SSRF, unsafe URL fetching, malicious HTML, CSV formula injection, and import validation;
- secure OAuth flow and PKCE where applicable;
- Windows Credential Manager or DPAPI-backed secret storage;
- least-privilege scopes;
- redaction of logs;
- encrypted backups where proportionate;
- file permissions;
- dependency and supply-chain controls;
- safe opening of external links;
- audit-event integrity;
- restore validation.

Provide a concise threat model and prioritised mitigations.

### 11. UK Data Protection and Direct-Marketing Controls

This is an architecture/compliance-control assessment, not legal advice.

Assess controls for:

- UK GDPR lawful-basis recording where personal data is processed;
- PECR distinction between corporate subscribers and sole traders/individual subscribers;
- social-media DMs as electronic mail;
- identity disclosure;
- opt-out mechanism;
- objection handling;
- suppression retention;
- data minimisation;
- source and collection date;
- retention review;
- privacy information;
- contact classification uncertainty;
- deletion versus minimal suppression evidence;
- auditability.

Identify points requiring professional legal review before production outreach.

### 12. Integration Designs

Provide individual recommendations for:

- Google Places or alternative business-discovery source;
- Instagram;
- Facebook;
- business websites;
- AI provider;
- Zoho Mail;
- optional Shopify catalogue synchronisation.

For each, define:

- MVP implementation;
- future implementation;
- fallback;
- stored identifiers;
- error handling;
- idempotency;
- security;
- cost controls.

### 13. Architecture Diagrams

Provide Mermaid diagrams for:

1. System context.
2. Container/component architecture.
3. Lead discovery and enrichment data flow.
4. Outreach approval and send flow.
5. Background-job state lifecycle.

Ensure diagrams match the recommended architecture.

### 14. Non-Functional Validation

Validate or revise:

- performance targets;
- capacity assumptions;
- availability/recovery expectations;
- backup objectives;
- restore objectives;
- maintainability;
- accessibility;
- observability;
- testability;
- Windows compatibility.

Add measurable NFRs for:

- maximum acceptable data loss;
- restore time;
- job recovery;
- API timeout/retry policy;
- audit retention;
- backup verification;
- AI response validation;
- accessibility target;
- supported Windows versions;
- log rotation.

### 15. Testing Strategy

Define:

- unit tests;
- domain/invariant tests;
- database migration tests;
- integration contract tests;
- provider-adapter tests;
- mocked failure tests;
- end-to-end workflows;
- security tests;
- backup/restore tests;
- AI golden-set evaluation;
- prompt regression tests;
- performance tests;
- acceptance testing for the pilot.

### 16. Delivery Roadmap

Produce a staged plan with:

- architecture runway;
- MVP slices that deliver usable outcomes early;
- dependencies;
- exit criteria;
- key technical spikes;
- pilot release;
- Phase 2;
- Phase 3.

Prefer vertical slices over building all infrastructure first.

### 17. Architecture Decision Records

Propose ADRs for at least:

- deployment model;
- modular-monolith pattern;
- backend language/framework;
- frontend framework;
- SQLite usage;
- persistent job scheduler;
- secrets storage;
- Google discovery strategy;
- assisted Meta workflow;
- AI provider abstraction;
- deterministic scoring;
- evidence/provenance model;
- Zoho integration boundary;
- backup strategy.

### 18. Cost and Build-vs-Buy Assessment

Provide cost categories and a method for estimating:

- Google Places/search calls;
- geocoding;
- AI tokens/requests;
- optional search providers;
- proxies or crawling infrastructure, if considered;
- Zoho development/integration;
- application maintenance.

Do not invent exact prices where not verified. Provide formulas, assumptions, and cost guardrails.

## Required Output Structure

Use the following structure:

1. Executive architecture verdict.
2. BRD/FSD quality scorecard.
3. Critical findings.
4. Scope amendments.
5. Feasibility assessment.
6. Options analysis and selected architecture.
7. Target architecture.
8. Component/module design.
9. Data architecture and logical model.
10. Discovery and enrichment design.
11. AI design.
12. Scheduling and background jobs.
13. Security and threat model.
14. Compliance-control design.
15. Integration recommendations.
16. Architecture diagrams.
17. NFR revisions.
18. Testing strategy.
19. Delivery roadmap.
20. Cost-control approach.
21. Architecture risks and mitigations.
22. Proposed ADR register.
23. Required BRD/FSD amendments.
24. Final recommendation and build/no-build decision.

## Quality Bar

- Be decisive and specific.
- Clearly label assumptions.
- Use requirement IDs when challenging the specification.
- Rank findings as Critical, High, Medium, or Low.
- Give implementable recommendations rather than generic best-practice statements.
- State when an item requires legal, platform-policy, or commercial validation.
- Preserve the core business intent while reducing unnecessary complexity.
- Do not fabricate API capabilities, permissions, costs, or legal conclusions.
