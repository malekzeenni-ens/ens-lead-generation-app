import { useCallback, useState } from "react";

/**
 * Per-screen view state that survives switching screens for the rest of the session:
 * filters, search, page, page size, view mode and which sections are open.
 *
 * Kept in sessionStorage when it is available, with an in-memory fallback, because
 * storage can be blocked or throw (private windows, previews). Never used for anything
 * that must persist reliably; that belongs to the backend.
 */
const memory = new Map<string, string>();
const PREFIX = "ens:view:";

function read(key: string): string | null {
  try {
    const stored = window.sessionStorage.getItem(PREFIX + key);
    if (stored !== null) return stored;
  } catch {
    // Storage blocked; fall back to memory.
  }
  return memory.get(key) ?? null;
}

function write(key: string, value: string): void {
  memory.set(key, value);
  try {
    window.sessionStorage.setItem(PREFIX + key, value);
  } catch {
    // Memory still holds it for this session.
  }
}

export function readRemembered<T>(key: string, fallback: T): T {
  const raw = read(key);
  if (raw === null) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function useRememberedState<T>(
  key: string | undefined,
  initial: T,
): [T, (next: T | ((current: T) => T)) => void] {
  const [value, setValue] = useState<T>(() => (key ? readRemembered(key, initial) : initial));
  const update = useCallback(
    (next: T | ((current: T) => T)) => {
      setValue((current) => {
        const resolved =
          typeof next === "function" ? (next as (current: T) => T)(current) : next;
        if (key) write(key, JSON.stringify(resolved));
        return resolved;
      });
    },
    [key],
  );
  return [value, update];
}

/** For tests: forget everything remembered. */
export function clearRememberedState(): void {
  memory.clear();
  try {
    for (let index = window.sessionStorage.length - 1; index >= 0; index -= 1) {
      const name = window.sessionStorage.key(index);
      if (name?.startsWith(PREFIX)) window.sessionStorage.removeItem(name);
    }
  } catch {
    // Nothing stored.
  }
}
