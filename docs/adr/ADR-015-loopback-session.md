# ADR-015: Loopback binding and ephemeral session token

- **Status:** Accepted
- **Context:** A desktop-wrapped HTTP API should not be reachable from the LAN or unauthorised local browser pages.
- **Decision:** Bind only to `127.0.0.1`; Tauri selects a local port, creates a cryptographically random token and supplies it to the backend/UI for the process lifetime. Restrict browser origins.
- **Alternatives considered:** `0.0.0.0`; fixed shared token; mandatory app password; no token.
- **Consequences:** Desktop/backend lifecycle coordination and port diagnostics are required. Local password remains optional for shared devices.
- **Security/compliance impact:** Limits local attack surface; token is not persisted or logged.
- **Rollback/migration:** Plain local-web fallback must generate a new launch token and retain loopback binding.

