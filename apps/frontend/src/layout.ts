import { useEffect, useState } from "react";

/** Below this width the sidebar shows icons only; below 900 px it becomes a top bar. */
export const NARROW_WINDOW_QUERY = "(max-width: 1180px) and (min-width: 901px)";

const SIDEBAR_KEY = "ens:layout:sidebar-collapsed";

/** Whether the operator collapsed the sidebar; kept between sessions. */
export function readSidebarCollapsed(): boolean {
  try {
    return window.localStorage.getItem(SIDEBAR_KEY) === "true";
  } catch {
    return false;
  }
}

export function writeSidebarCollapsed(collapsed: boolean): void {
  try {
    if (collapsed) window.localStorage.setItem(SIDEBAR_KEY, "true");
    else window.localStorage.removeItem(SIDEBAR_KEY);
  } catch {
    // Storage unavailable: the choice lasts for this session only.
  }
}

function matches(query: string): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia(query).matches;
}

export function useMediaQuery(query: string): boolean {
  const [isMatch, setIsMatch] = useState(() => matches(query));
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const list = window.matchMedia(query);
    const update = () => setIsMatch(list.matches);
    update();
    list.addEventListener("change", update);
    return () => list.removeEventListener("change", update);
  }, [query]);
  return isMatch;
}
