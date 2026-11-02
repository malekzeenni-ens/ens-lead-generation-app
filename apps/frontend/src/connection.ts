/**
 * Which way this page reaches the backend (ADR-025).
 *
 * - desktop: inside the Tauri window, which hands over the loopback address and session token;
 *   or a development browser given both through Vite env values.
 * - phone: a production build served by the phone gateway, which uses the same origin and a
 *   paired-device cookie instead of a token.
 */
export type ConnectionMode = "desktop" | "phone";

export function connectionMode(): ConnectionMode {
  if (typeof window !== "undefined" && window.__TAURI_INTERNALS__) return "desktop";
  if (import.meta.env.VITE_ENS_API_URL) return "desktop";
  return import.meta.env.PROD ? "phone" : "desktop";
}

export function isPhoneMode(): boolean {
  return connectionMode() === "phone";
}
