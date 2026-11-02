import { openUrl } from "@tauri-apps/plugin-opener";

import { isPhoneMode } from "./connection";

/** Open a web page or a mail draft outside the app. */
export async function openExternalUrl(url: string): Promise<void> {
  if (window.__TAURI_INTERNALS__) {
    await openUrl(url);
    return;
  }
  // A phone blocks a new window opened after waiting on the PC. A mail link hands over to the
  // mail app without leaving this page, so it is followed in place.
  if (isPhoneMode() && url.startsWith("mailto:")) {
    window.location.assign(url);
    return;
  }
  const browser = window.open(url, "_blank", "noopener,noreferrer");
  if (!browser) throw new Error("The browser blocked the external window.");
}
