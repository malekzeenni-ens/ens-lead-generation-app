# ADR-004: FastAPI and Python backend

- **Status:** Accepted
- **Context:** Validation, local APIs, data processing and later AI/provider adapters need a productive typed ecosystem.
- **Decision:** Use Python 3.13, FastAPI, Pydantic, SQLAlchemy 2 and explicit service/repository boundaries.
- **Alternatives considered:** ASP.NET Core; Rust-only Tauri commands; Node/TypeScript service.
- **Consequences:** Python must be packaged as a managed sidecar for release; OpenAPI provides the client contract.
- **Security/compliance impact:** Central validation and error handling; the process accepts loopback traffic only.
- **Rollback/migration:** Provider-neutral contracts and SQL schema permit another service implementation later.

