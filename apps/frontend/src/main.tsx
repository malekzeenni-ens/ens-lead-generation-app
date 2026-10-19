import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import { applyDensity, applyTheme, readDensity, readTheme } from "./appearance";
import "./styles.css";

// Before the first paint, so a light-theme user never sees a dark flash.
applyTheme(readTheme());
applyDensity(readDensity());

const root = document.getElementById("root");
if (!root) {
  throw new Error("Application root was not found");
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

