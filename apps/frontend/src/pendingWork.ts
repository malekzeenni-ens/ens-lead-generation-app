import { useSyncExternalStore } from "react";

/**
 * Work the phone is waiting on the PC for: a change being saved, an AI answer, or a background
 * job being followed. The phone shows one calm indicator for all of it, so a slow PC never looks
 * like a frozen screen.
 */
export type PendingKind = "change" | "ai" | "job";

export interface PendingItem {
  id: number;
  kind: PendingKind;
  startedAt: number;
  progress?: { current: number; total: number };
}

let nextId = 1;
let items: PendingItem[] = [];
const listeners = new Set<() => void>();

function emit(): void {
  for (const listener of listeners) listener();
}

/** Start tracking; the returned handle updates progress and ends it. */
export function beginPending(kind: PendingKind): {
  progress: (current: number, total: number) => void;
  end: () => void;
} {
  const id = nextId++;
  items = [...items, { id, kind, startedAt: Date.now() }];
  emit();
  return {
    progress(current, total) {
      items = items.map((item) => (item.id === id ? { ...item, progress: { current, total } } : item));
      emit();
    },
    end() {
      items = items.filter((item) => item.id !== id);
      emit();
    },
  };
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function snapshot(): PendingItem[] {
  return items;
}

export function usePendingWork(): PendingItem[] {
  return useSyncExternalStore(subscribe, snapshot, snapshot);
}

/** For tests: forget anything still tracked. */
export function clearPendingWork(): void {
  items = [];
  emit();
}
