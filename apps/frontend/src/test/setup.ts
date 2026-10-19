import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

import { clearRememberedState } from "../remembered";

afterEach(() => {
  cleanup();
  // Remembered filters, pages and open sections must not leak between tests.
  clearRememberedState();
  // So do the sidebar and appearance choices kept in local storage.
  window.localStorage.clear();
  delete document.documentElement.dataset.theme;
  delete document.documentElement.dataset.density;
});
