import { type ReactNode } from "react";

import { AppearanceContext, useAppearanceState } from "../appearance";

/** Appearance is independent of workspace/server state and never remounts its children. */
export function AppearanceProvider({ children }: { children: ReactNode }) {
  const appearance = useAppearanceState();
  return <AppearanceContext.Provider value={appearance}>{children}</AppearanceContext.Provider>;
}
