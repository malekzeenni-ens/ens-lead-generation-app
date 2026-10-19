import { Maximize2, Minimize2, Sparkles, X } from "lucide-react";
import { type KeyboardEvent, type ReactNode, useEffect, useRef, useState } from "react";

interface AssistantLauncherProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Shows a warning dot on the button once the assistant reports the local model is not ready. */
  needsSetup: boolean;
  children: ReactNode;
}

/**
 * The AI assistant as a floating button, bottom-right on every screen, like a website's
 * "contact us" bubble. The panel is created on first open and kept mounted afterwards,
 * so a conversation survives closing and reopening it.
 */
export function AssistantLauncher({ open, onOpenChange, needsSetup, children }: AssistantLauncherProps) {
  const [created, setCreated] = useState(open);
  const [wide, setWide] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const wasOpen = useRef(open);
  const restoreFocus = useRef(false);

  if (open && !created) setCreated(true);

  useEffect(() => {
    if (open && !wasOpen.current) panelRef.current?.focus();
    if (!open && restoreFocus.current) {
      restoreFocus.current = false;
      buttonRef.current?.focus();
    }
    wasOpen.current = open;
  }, [open]);

  function close(): void {
    restoreFocus.current = true;
    onOpenChange(false);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>): void {
    if (event.key !== "Escape") return;
    event.stopPropagation();
    close();
  }

  return (
    <>
      {created ? (
        <div
          ref={panelRef}
          id="assistant-panel"
          className={`assistant-panel${wide ? " assistant-panel--wide" : ""}`}
          role="dialog"
          aria-modal="false"
          aria-labelledby="assistant-panel-title"
          tabIndex={-1}
          hidden={!open}
          onKeyDown={handleKeyDown}
        >
          <header className="assistant-panel__header">
            <span className="assistant-panel__mark" aria-hidden="true">
              <Sparkles size={18} />
            </span>
            <div>
              <h2 id="assistant-panel-title">AI assistant</h2>
              <p>Private · runs on this computer</p>
            </div>
            <button
              type="button"
              className="icon-button"
              aria-pressed={wide}
              aria-label={wide ? "Narrow the assistant" : "Widen the assistant"}
              title={wide ? "Narrow" : "Widen"}
              onClick={() => setWide((current) => !current)}
            >
              {wide ? <Minimize2 size={17} aria-hidden="true" /> : <Maximize2 size={17} aria-hidden="true" />}
            </button>
            <button
              type="button"
              className="icon-button"
              aria-label="Close AI assistant"
              title="Close"
              onClick={close}
            >
              <X size={18} aria-hidden="true" />
            </button>
          </header>
          <div className="assistant-panel__body">{children}</div>
        </div>
      ) : null}
      {open ? null : (
        <button
          ref={buttonRef}
          type="button"
          className="assistant-launcher"
          aria-label="Open AI assistant"
          aria-expanded={false}
          aria-haspopup="dialog"
          onClick={() => onOpenChange(true)}
        >
          <Sparkles size={22} aria-hidden="true" />
          <span className="assistant-launcher__label" aria-hidden="true">Ask AI</span>
          {needsSetup ? (
            <span className="assistant-launcher__dot" title="The local AI model needs setting up" />
          ) : null}
        </button>
      )}
    </>
  );
}
