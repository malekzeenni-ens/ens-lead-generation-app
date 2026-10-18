# ADR-024: The audit log holds no personal data; outreach history lives with the lead

- **Status:** Accepted (operator decision D2, 18 October 2026)
- **Context:** Audit events outlive privacy deletion. A lead's outreach timeline was rebuilt from audit-event JSON, so `outreach.zoho_open_clicked` and `outreach.zoho_open_failed` stored the recipient's email address and the operator's reason, and `confirm_sent` refused to proceed unless a particular audit event existed. Other events stored the business name (`lead.created`), every changed lead field's before and after values including contact names and emails (`lead.updated`), and free-text reasons. Deleting a lead (FR-163) left all of that behind.
- **Decision:** Business state lives in domain tables that are deleted with the lead. Audit events record IDs, versions, counts, enums, hashes and field names only, and `record_audit_event` refuses a summary that names a personal-data key at any depth.

## What changed

- New table `outreach_activity` (lead ID, draft ID, action, version, reason, recipient email, time), cascading from the lead and the draft. Every outreach step writes one row and one audit event through `outreach/activity.py`. The lead API's `outreach_activities` is unchanged and now reads this table.
- `outreach_draft.zoho_opened_at` replaces the audit lookup in `confirm_sent`.
- `lead.updated` records `changed_fields` for every change, and before/after values only for structured, non-personal fields (statuses, values, dates, segment, classification).
- `reason` becomes `reason_provided: true|false`; the reason itself stays in its domain record (stage event, draft, candidate, score override).
- `lead.created` no longer records the business name.
- `AuditRepository` was removed; nothing reads audit events for business decisions.

## Historic data

Migration `0018_outreach_activity` backfills `outreach_activity` and `zoho_opened_at` from existing audit events, keeping each event's ID and time, then rewrites every historic audit summary under the same rules. The rewrite cannot be undone. Before any pending migration runs on an existing database, `run_migrations` writes `<name>.pre-upgrade-<revision>-<UTC time>.sqlite3` beside it. That copy is the way back, and it still holds the removed data, so the operator deletes it once the upgraded app has been checked.

## Consequences

- The guard turns a future leak into a failing test. `test_audit_minimisation.py` also scans every `record_audit_event` call site for literal personal-data keys, covering paths the suite does not exercise.
- The audit log still answers "what happened, when, to which record, by whom", but not "what did it say". That detail lives with the record and goes when the record goes.
