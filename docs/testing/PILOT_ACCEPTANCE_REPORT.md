# Pilot acceptance report

**Assessment:** Increment 1 engineering proof accepted; product pilot not yet accepted  
**Date:** 18 July 2026

## Proven journey

On the Windows kickoff machine, the implementation can start the packaged local backend under Tauri control, authenticate over loopback, migrate a fresh SQLite database, create a Luton-focused campaign, add a manual lead with source attribution and unresolved contact classification, persist stage/audit records, survive a database reopen, create and verify a backup, and restore it to an isolated path. The signed-off quality suites and packaged release smoke pass.

## Acceptance results

| Criterion | Result |
|---|---|
| Local-first campaign/manual lead workflow | Pass |
| Source evidence separate from canonical data | Pass |
| Loopback/session/API error controls | Pass |
| Migration, restart, backup and isolated restore | Pass |
| Windows sidecar and NSIS production build | Pass for engineering smoke |
| Etch ’N’ Shine central colour/spacing/focus tokens | Pass by implementation review |
| Full Stage 1 workflow | Not complete |
| External discovery, AI, Zoho, or sending | Deliberately absent |
| Clean-profile installer/upgrade/uninstall | Not run |
| Legal/privacy production-outreach approval | Open |
| Signed production artefact | Open |

## Decision

Use this increment as the foundation for Stage 1 development and controlled internal engineering evaluation. Do not begin operational prospecting or distribute a production installer yet. Pilot acceptance requires the remaining Stage 1 workflow (including suppression), keyboard/resolution review, clean-profile installer exercise, support/recovery rehearsal, signed artefact plan, and owner/legal/privacy control sign-off.
