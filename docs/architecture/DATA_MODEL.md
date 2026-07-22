# Data model

**Schema revision:** `0005_contact_social`  
**Database:** SQLite with WAL, foreign keys, five-second busy timeout

## Implemented entities

| Table | Purpose and key invariants |
|---|---|
| `campaign` | Unique campaign name; positive radius; shortlist size 1–50; score threshold 0–100; structured discovery/channel/offer settings |
| `lead` | Canonical business identity/classification plus website, phone and public email; pipeline, opportunity/commercial status, retention date and indexed suppression state |
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
| `campaign_run` | Durable operator-triggered campaign execution with batch, phase/status, provider state, counters, warnings/errors, cancellation and timings |
| `discovery_candidate` | Staged provider business evidence and duplicate/promotion/rejection decision, separate from canonical leads |
| `provider_attempt` | Bounded provider query/request/result counts and safe terminal error evidence for a campaign run |

```text
campaign 1 ──< lead_campaign >── 1 lead
                                   ├──< source_observation >── source_system
                                   ├──< lead_stage_event
                                   ├──< lead_note
                                   ├──< follow_up
                                   ├──< communication
                                   └──< suppression_record (nullable lead link)

audit_event references entities logically to remain immutable
backup_manifest records completed backup evidence
product supplies deterministic product matches to score runs and shortlist items
campaign 1 â”€â”€< score_run >â”€â”€ 1 lead
campaign 1 â”€â”€< shortlist 1 â”€â”€< shortlist_item >â”€â”€ 1 lead
```

## Canonical versus observed data

`lead.business_name`, location, website, phone number, public email, and preferred social profile are operational canonical fields. Platform-specific identities are retained in `lead_social_identity`. Source claims remain in `source_observation`; they are not flattened into a last-write-wins provider payload.

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

## Planned schema increments

Lead CSV import remains intentionally absent. Later stages add richer evidence resolution and merge history, general-purpose leased jobs/retries/budgets, AI runs, draft/version/approval models, and integration mappings. Shopify API synchronisation is also deferred; revision `0005_contact_social` retains only normalised product/provider evidence rather than raw files or provider payloads.
