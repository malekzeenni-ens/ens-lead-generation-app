# Compliance control register

This is an engineering control register, not legal advice. A qualified UK legal/privacy review and business-owner sign-off are required before production outreach.

| ID | Control | Current state | Release gate/evidence |
|---|---|---|---|
| CMP-001 | Record source and collection time for prospect data | Implemented for manual, Google, official Instagram and public-website observations | Backend integration test and provider candidate evidence |
| CMP-002 | Classify contact as corporate, sole trader/individual, individual-treatment partnership, or unknown | Implemented; unknown visibly flagged | API/UI tests; operator review still required |
| CMP-003 | Preserve canonical values separately from source observations | Implemented foundation | Data model and integration test |
| CMP-004 | Suppression overrides shortlist, drafting, approval, sending, and retries | Implemented at shortlist and all existing local outreach-record boundaries; drafting/sending/retries do not yet exist | Backend shortlist/suppression integration test; repeat the server-side gate at every future outreach boundary |
| CMP-005 | Record lawful-basis/PECR assessment and approved privacy wording by audience/channel | Open business/legal decision | Written review and owner sign-off |
| CMP-006 | Provide privacy notice, objection/opt-out handling, and subject-rights workflow | Planned | Stage 1–4 acceptance tests/runbook |
| CMP-007 | Define retention periods and reviewed deletion/anonymisation | Open business/legal decision | Approved schedule plus implementation tests |
| CMP-008 | Restrict data collection to necessary public/provided fields | Manual form, Google field mask, bounded Meta fields and homepage evidence parser are bounded; raw responses/HTML are not retained | Review every adapter and AI packet |
| CMP-009 | Human approval before external communication | No send feature exists | Server-side approval and suppression tests before enablement |
| CMP-010 | Keep evidence of message/draft versions, approver, sender/channel/time/outcome | Planned | Stage 4 audit/communication tests |
| CMP-011 | Processor/DPA and international-transfer review for AI/CRM/provider services | Open | Provider-specific documented decision |
| CMP-012 | Platform terms and API authorisation, especially Meta | Google and bounded official Instagram test paths implemented; Meta app-role testing only; owner terms/review/billing sign-off remains open | ADR-016, Meta permission evidence and approved production capability |
| CMP-013 | Credential access, revocation, incident, and breach handling | Google key is backend environment-only; Meta credentials/tokens use current-user DPAPI with disconnect/remove controls | Token rotation/revocation and incident-runbook exercise |
| CMP-014 | Backup access, retention, off-device copy, and restore testing | Technical backup implemented | Owner-selected protected location and recovery drill |
| CMP-015 | Data-quality correction and duplicate/merge evidence | Provider/exact website/name matches link; fuzzy names are staged for audited operator decision; general merge remains unimplemented | Discovery integration tests; richer resolution/merge tests |

## Hard stop

Production outreach remains prohibited while CMP-005 is open. CMP-004 is closed for the current local shortlist workflow, but any future draft, approval, send, or retry feature must add and verify the same server-side suppression override before it may be enabled. Only the bounded, operator-triggered Instagram discovery path in ADR-016 is approved for app-role testing; Meta messaging, browser automation, broader discovery and autonomous commercial commitments remain outside approved scope.

## Review cadence

Update this register with every data source, audience, communication channel, AI provider, CRM integration, retention change, incident, or material legal/policy change. Record reviewer, date, evidence link, decision, and any expiry/re-review date in the delivery log or a linked decision record.
