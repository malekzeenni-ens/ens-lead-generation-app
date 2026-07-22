# ADR-003: React and strict TypeScript frontend

- **Status:** Accepted
- **Context:** The desktop UI needs accessible forms, typed API contracts and rapid iteration.
- **Decision:** Use React, strict TypeScript and Vite; use focused components and semantic HTML.
- **Alternatives considered:** Vue; Svelte; native Tauri UI.
- **Consequences:** Node tooling and frontend lockfiles are required; server business rules must not move into components.
- **Security/compliance impact:** External content is rendered as text, never raw HTML; secrets are not stored in browser storage.
- **Rollback/migration:** The HTTP/OpenAPI boundary allows a different client without changing domain services.

