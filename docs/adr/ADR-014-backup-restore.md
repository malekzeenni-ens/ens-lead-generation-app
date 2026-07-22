# ADR-014: SQLite-native backup and verified restore

- **Status:** Accepted
- **Context:** Copying a live WAL database can be inconsistent; pilot release requires demonstrable recovery.
- **Decision:** Use SQLite's backup API, integrity check, SHA-256 manifest and schema/application metadata; verify and restore into an isolated path before replacement.
- **Alternatives considered:** Blind file copy; export-only recovery; filesystem snapshots.
- **Consequences:** Restore of the active database is an explicit stopped-app maintenance operation. RPO is 24 hours scheduled/zero manual; RTO target is 30 minutes.
- **Security/compliance impact:** Backup location/ACL warnings and later optional encryption protect lead data.
- **Rollback/migration:** Backups are non-destructive; active replacement requires a pre-restore backup and recovery instructions.

