/** Helpers for the phone pairing screen (ADR-025). */

/** A short, readable label for the devices list on the PC, e.g. "Safari on iPhone". */
export function browserLabel(userAgent: string): string {
  const device = /iPhone/.test(userAgent)
    ? "iPhone"
    : /iPad/.test(userAgent)
      ? "iPad"
      : /Android/.test(userAgent)
        ? "Android"
        : "phone";
  const browser = /EdgA?\//.test(userAgent)
    ? "Edge"
    : /SamsungBrowser/.test(userAgent)
      ? "Samsung Internet"
      : /CriOS|Chrome\//.test(userAgent)
        ? "Chrome"
        : /FxiOS|Firefox\//.test(userAgent)
          ? "Firefox"
          : /Safari\//.test(userAgent)
            ? "Safari"
            : "Browser";
  return `${browser} on ${device}`;
}

/** The pairing code from a QR link such as /pair#K7QM-4T9X, if this page was opened by one. */
export function codeFromLocation(location: Pick<Location, "pathname" | "hash">): string {
  if (!location.pathname.startsWith("/pair")) return "";
  return decodeURIComponent(location.hash.replace(/^#/, "")).slice(0, 20);
}
