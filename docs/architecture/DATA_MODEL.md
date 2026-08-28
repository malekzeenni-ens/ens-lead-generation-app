# Data model

**Schema revision:** `0011_weekly_outreach_automation`
**Database:** SQLite with WAL, foreign keys, five-second busy timeout

## Implemented entities

| Table | Purpose and key invariants |
|---|---|
| `campaign` | Unique campaign name; positive radius; shortlist size 1–50; score threshold 0–100; structured discovery/channel/offer settings; opt-in weekly template and refresh provider |
| `lead` | Canonical business identity/classification plus website, phone and public email; one primary contact; reusable email context; pipeline, opportunity/commercial status, retention date, structured outreach hold and indexed suppression state |
| `lead_campaign` | Many-to-many campaign membership with `added_at`; composite primary key |
| `lead_social_identity` | Unique platform/profile and platform/handle identity linked to one canonical lead, with source, classification and collection time |
| `source_system` | Provider-neutral source identity and type |
| `source_observation` | Append-style observed value, field, source URL, classification, method, and collection time, separate from canonical lead data |
| `lead_stage_event` | Pipeline history with previous/new stage, actor, reason, time |
| `lead_note` | Timestamped local note owned by a lead |
| `follow_up` | Typed due date, notes and open/completed/cancelled state |
| `communication` | Channel, content snapshot, draft/sent/received state, sent confirmation, external ID and reply outcome |
| `suppression_record` | Objection/unsubscribe/do-not-contact evidence; active records can survive lead deletion via a minimised identity hash |
| `app_setting` | Validated local operating defaults stored as key/value records |
| `audit_event` | Append-only application audit summary with action, entity, actor, correlation ID, time |
| `backup_manifest` | Backup filename, SHA-256 checksum, integrity result, schema/app version, time |
| `product` | Editable catalogue item; optional unique Shopify handle, category, descriptions, segment/use-case lists, price/image guidance, active/sample flags and import provenance |
| `scoring_profile` | Immutable version of a named segment scoring profile; seven validated weights total 100 and exactly one active version per segment |
| `score_run` | Historical deterministic calculation with profile/rule versions, category breakdown, evidence/missing fields, product-match snapshot, optional campaign-run/fingerprint links, manual override and final score |
| `shortlist` | Unique campaign/week selection run with requested/effective capacity, status and generation time |
| `shortlist_item` | Ranked lead recommendation with score, visible reasons, product-match snapshot and operator decision state |
| `campaign_run` | Durable manual or first-open weekly execution with batch, optional week/batch link, phase/status, provider state, counters, warnings/errors, cancellation and timings; one weekly run per campaign/week |
| `discovery_candidate` | Staged provider business evidence and duplicate/promotion/rejection decision, separate from canonical leads |
| `provider_attempt` | Bounded provider query/request/result counts and safe terminal error evidence for a campaign run |
| `outreach_batch` | One local template/campaign preparation run with derived review/ready/closed state |
| `outreach_draft` | Lead/recipient snapshot with pending/approved/rejected review state, local sync state and approval-version evidence |
| `outreach_draft_revision` | Immutable subject/body version with content hash, editor and creation time; one current version per draft |

```text
campaign 1 ──< lead_campaign >── 1 lead
                                   ├──< source_observation >── source_system
                                   ├──< lead_stage_event
                                   ├──< lead_note
                                   ├──< follow_up
                                   ├──< communication
                                   ├──< outreach_draft >── outreach_batch
                                   │                       └──< outreach_draft_revision
                                   └──< suppression_record (nullable lead link)

audit_event references entities logically to remain immutable
backup_manifest records completed backup evidence
product supplies deterministic product matches to score runs and shortlist items
campaign 1 â”€â”€< score_run >â”€â”€ 1 lead
campaign 1 â”€â”€< shortlist 1 â”€â”€< shortlist_item >â”€â”€ 1 lead
```

## Canonical versus observed data

`lead.business_name`, location, website, phone number, public email, primary-contact name/role/direct email, email context, and preferred social profile are operational canonical fields. This intentionally models one primary contact rather than a general-purpose multi-contact CRM. Platform-specific identities are retained in `lead_social_identity`. Source claims remain in `source_observation`; the primary contact has a separate operator-entered source/reference field.

Email context is split into an evidence-based observation, its relevance, the offer angle, one desired next step, and an internal avoid-mentioning guardrail. The first four can be selected explicitly in templates. The guardrail and contact-source reference are never inserted into a draft token. `greeting_name` uses the contact first name and falls back to the business name.

Lead names are Unicode-normalised, trimmed, whitespace-collapsed, and case-folded for comparison. The current duplicate check is deliberately conservative: an exact normalised name and case-folded location returns a review conflict rather than silently merging records.

## Transaction rules

- Lead, campaign membership, source system/observation, initial stage event, and audit event commit together.
- Domain failures roll back the unit of work.
- Foreign keys are enforced on every connection.
- Schema changes run through Alembic before API traffic is accepted.
- Active WAL files are never copied as the backup mechanism; SQLite’s backup API creates a consistent snapshot.
- Suppression records use a nullable lead reference so privacy deletion can remove the personal activity graph while retaining a minimised matching hash.
- An active suppression immediately removes a recommended/approved shortlist item and overrides shortlist eligibility.
- Scoring-profile updates create a new version; historical score runs retain their original profile and rule snapshot.
- Shopify imports upsert products by case-folded handle, collapse variants, and never store the uploaded raw CSV.
- Provider and assisted-social results enter `discovery_candidate` first. Exact provider/social-handle/website/phone/email/name matches link to existing leads; high-confidence fuzzy names wait for operator review; accepted new businesses are promoted transactionally with campaign membership, contacts, evidence and initial stage history.
- Current-week campaign automation never overwrites an existing shortlist. Unchanged deterministic inputs reuse the latest score run by SHA-256 fingerprint.
- The first app opening in a local calendar week creates at most one weekly run per enabled campaign. Opening on Tuesday or later catches up that same week without creating missed-week backlog.
- Weekly campaigns execute sequentially. Draft preparation failures are isolated to one campaign and can be retried on the same durable run.
- A lead shortlisted by several campaigns receives at most one weekly draft: the highest campaign-specific score wins, followed by rank and a stable campaign-name tie-break. The workspace-wide weekly cap is applied after this deduplication.
- Draft creation and approval both re-check suppression, pipeline stage, a valid direct-contact or public business email, contact classification, outreach hold and active-draft conflicts. A valid direct email takes recipient priority. Lead contact/context/stage/hold changes invalidate an existing approval.
- Draft edits append a revision and clear approval. Rejection changes only the draft, retains it locally and can be reopened; email content is not copied into audit summaries.
- An approved draft may move from `local_only` to `opened_in_zoho` after a fresh server-side check. Each request is audited before the desktop composer opens; a reported composer failure returns it to `local_only`.
- `user_confirmed_sent` is terminal for that draft. Confirmation creates a normal email `communication` containing the approved subject/body, sent time and `user_confirmed=true`; it does not change the lead's pipeline stage.

## Planned schema increments

Lead CSV import remains intentionally absent. Later stages add richer evidence resolution and merge history, general-purpose leased jobs/budgets, AI runs, and integration mappings. Revision `0011_weekly_outreach_automation` performs catch-up when the local app opens; it is not an operating-system scheduler and cannot run while the app is closed. Zoho API draft sync and automatic outbound sending remain deferred; the assisted `mailto:` handoff reuses the existing draft status and communication records. Shopify API synchronisation is also deferred; the schema retains only normalised product/provider evidence rather than raw files or provider payloads.
