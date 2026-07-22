/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_ENS_API_URL?: string;
  readonly VITE_ENS_SESSION_TOKEN?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

interface Window {
  __TAURI_INTERNALS__?: unknown;
}

