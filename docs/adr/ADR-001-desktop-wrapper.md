# ADR-001: Tauri desktop wrapper

- **Status:** Accepted
- **Context:** A single Windows user needs a polished local application, browser-assisted links and managed backend lifecycle without Electron's footprint.
- **Decision:** Use Tauri 2 to host the React UI, start/monitor/stop the local backend and produce signing-capable Windows bundles.
- **Alternatives considered:** Plain localhost browser app; Electron; native .NET.
- **Consequences:** Rust/WebView2 and Python-sidecar packaging must be tested. The plain local web app remains the fallback.
- **Security/compliance impact:** Native shell privileges stay minimal; external links open in the system browser; API stays loopback/token protected.
- **Rollback/migration:** Remove the wrapper and retain the frontend/API as a localhost application.

