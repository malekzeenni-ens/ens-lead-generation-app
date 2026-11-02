import { Moon, Sun } from "lucide-react";
import { useId } from "react";

import { useAppearance } from "../appearance";

export function AppearanceControl() {
  const { theme, effectiveTheme, setTheme } = useAppearance();
  const descriptionId = useId();
  return (
    <div className="appearance-control">
      <div className="appearance-segments" role="group" aria-label="Appearance" aria-describedby={descriptionId}>
        <button type="button" aria-label="Dark theme" aria-pressed={effectiveTheme === "dark"} onClick={() => setTheme("dark")}>
          <Moon size={17} aria-hidden="true" /><span>Dark</span>
        </button>
        <button type="button" aria-label="Bright theme" aria-pressed={effectiveTheme === "light"} onClick={() => setTheme("light")}>
          <Sun size={17} aria-hidden="true" /><span>Bright</span>
        </button>
      </div>
      <span className="appearance-system" data-following={theme === "system"} aria-hidden="true">System</span>
      <span id={descriptionId} className="visually-hidden">
        {theme === "system"
          ? `Following Windows appearance. Currently ${effectiveTheme === "light" ? "Bright" : "Dark"}. Choose a mode to override, or use Match Windows in Settings.`
          : "Choose Dark or Bright. Match Windows is available in Settings."}
      </span>
    </div>
  );
}
