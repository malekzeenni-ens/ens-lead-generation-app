import { LoaderCircle } from "lucide-react";
import { useEffect, useState } from "react";

import { type PendingItem, usePendingWork } from "../pendingWork";

// Quick answers never flash a loader; slow ones explain that the PC carries on regardless.
export const SHOW_AFTER_MS = 400;
export const REASSURE_AFTER_MS = 10_000;

function describe(item: PendingItem): string {
  if (item.kind === "ai") return "Thinking on your PC…";
  if (item.kind === "job") {
    const progress = item.progress;
    return progress && progress.total > 0
      ? `Working on your PC… ${progress.current} of ${progress.total}`
      : "Working on your PC…";
  }
  return "Saving on your PC…";
}

/** The one place a phone shows that it is waiting for the PC (mobile plan, operator request). */
export function PendingWorkIndicator() {
  const items = usePendingWork();
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (items.length === 0) return;
    const timer = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(timer);
  }, [items.length]);

  const visible = items.filter((item) => now - item.startedAt >= SHOW_AFTER_MS);
  // The longest-running item speaks for all of them; an AI answer or a job is more telling
  // than a save that started at the same time.
  const rank = { ai: 0, job: 1, change: 2 } as const;
  const lead = [...visible].sort(
    (first, second) => rank[first.kind] - rank[second.kind] || first.startedAt - second.startedAt,
  )[0];
  const slow = lead ? now - lead.startedAt >= REASSURE_AFTER_MS : false;

  return (
    <div className="pending-work" role="status" aria-live="polite" data-visible={lead ? "true" : "false"}>
      {lead ? (
        <>
          <LoaderCircle className="spin" size={18} aria-hidden="true" />
          <span className="pending-work__text">
            <strong>{describe(lead)}</strong>
            {slow ? (
              <small>
                {lead.kind === "change"
                  ? "Your PC is taking a while. Keep this screen open."
                  : "This carries on on your PC even if you leave this screen."}
              </small>
            ) : null}
          </span>
          {visible.length > 1 ? <span className="pending-work__count">+{visible.length - 1}</span> : null}
        </>
      ) : null}
    </div>
  );
}
