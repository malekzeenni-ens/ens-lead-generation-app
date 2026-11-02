import { createContext, useCallback, useContext, useEffect, useState } from "react";

/**
 * Per-computer display preferences (UX redesign E1, E2). They change only how the app
 * looks, so they live in this browser profile rather than in the workspace database.
 */
export type ThemeChoice = "system" | "light" | "dark";
export type DensityChoice = "comfortable" | "compact";

const THEME_KEY = "ens:appearance:theme";
const DENSITY_KEY = "ens:appearance:density";

function read<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  try {
    const value = window.localStorage.getItem(key);
    return allowed.includes(value as T) ? (value as T) : fallback;
  } catch {
    return fallback;
  }
}

function write(key: string, value: string, fallback: string): void {
  try {
    if (value === fallback) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    // Storage unavailable: the choice lasts until the app is closed.
  }
}

export function readTheme(): ThemeChoice {
  return read(THEME_KEY, ["system", "light", "dark"] as const, "system");
}

export function readDensity(): DensityChoice {
  return read(DENSITY_KEY, ["comfortable", "compact"] as const, "comfortable");
}

/** "system" leaves the theme to the operating system's light or dark setting. */
export function applyTheme(theme: ThemeChoice): void {
  if (theme === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
}

export function applyDensity(density: DensityChoice): void {
  if (density === "comfortable") delete document.documentElement.dataset.density;
  else document.documentElement.dataset.density = density;
}

export function useAppearanceState() {
  const [theme, setThemeState] = useState(readTheme);
  const [density, setDensityState] = useState(readDensity);
  const [systemIsLight, setSystemIsLight] = useState(
    () => typeof window.matchMedia === "function" && window.matchMedia("(prefers-color-scheme: light)").matches,
  );

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const media = window.matchMedia("(prefers-color-scheme: light)");
    const update = () => setSystemIsLight(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  const setTheme = useCallback((next: ThemeChoice) => {
    write(THEME_KEY, next, "system");
    setThemeState(next);
    applyTheme(next);
  }, []);
  const setDensity = useCallback((next: DensityChoice) => {
    write(DENSITY_KEY, next, "comfortable");
    setDensityState(next);
    applyDensity(next);
  }, []);
  const effectiveTheme: "light" | "dark" = theme === "system"
    ? (systemIsLight ? "light" : "dark")
    : theme;
  return { theme, setTheme, effectiveTheme, density, setDensity };
}

export const AppearanceContext = createContext<ReturnType<typeof useAppearanceState> | null>(null);

/** Header and Settings consume one owner; storage is not used as a same-window event bus. */
export function useAppearance() {
  const appearance = useContext(AppearanceContext);
  if (!appearance) throw new Error("Appearance controls require AppearanceProvider.");
  return appearance;
}
