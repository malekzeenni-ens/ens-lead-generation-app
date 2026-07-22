# ADR-013: Zoho draft before integrated send

- **Status:** Accepted
- **Context:** Sending is externally irreversible and requires OAuth, idempotency and uncertain-result reconciliation.
- **Decision:** MVP copies approved content for manual Zoho use. Phase 2 first creates/reconciles drafts; direct send requires a separate readiness decision.
- **Alternatives considered:** Direct send in MVP; SMTP; no Zoho path.
- **Consequences:** Manual confirmation remains authoritative in MVP.
- **Security/compliance impact:** Approval content hash, suppression and contact checks remain transactionally enforced; least-privilege OAuth is mandatory later.
- **Rollback/migration:** Disable the adapter; retain local draft/communication history.

