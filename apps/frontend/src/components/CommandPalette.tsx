import { CornerDownLeft, Search } from "lucide-react";
import { type KeyboardEvent, useEffect, useId, useMemo, useRef, useState } from "react";

export interface PaletteItem {
  id: string;
  group: string;
  label: string;
  hint?: string;
  run: () => void;
}

interface CommandPaletteProps {
  onClose: () => void;
  items: PaletteItem[];
}

const GROUP_ORDER = ["Go to", "Actions", "Leads", "Campaigns", "Products", "Templates"];
const PER_GROUP = 6;

/** Ctrl+K search across screens, records already loaded, and quick actions. Mounted only while open. */
export function CommandPalette({ onClose, items }: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listId = useId();

  useEffect(() => {
    const returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    inputRef.current?.focus();
    return () => returnFocus?.focus();
  }, []);

  const results = useMemo(() => {
    const search = query.trim().toLocaleLowerCase();
    const matching = items.filter((item) =>
      search
        ? `${item.label} ${item.hint ?? ""}`.toLocaleLowerCase().includes(search)
        : item.group === "Go to" || item.group === "Actions",
    );
    const grouped = GROUP_ORDER.map((group) => ({
      group,
      items: matching.filter((item) => item.group === group).slice(0, PER_GROUP),
    })).filter((entry) => entry.items.length > 0);
    return { grouped, flat: grouped.flatMap((entry) => entry.items) };
  }, [items, query]);

  function choose(item: PaletteItem | undefined): void {
    if (!item) return;
    onClose();
    item.run();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>): void {
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((current) => Math.min(current + 1, results.flat.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((current) => Math.max(current - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      choose(results.flat[active]);
    } else if (event.key === "Tab") {
      event.preventDefault();
    }
  }

  const activeItem = results.flat[active];

  return (
    <div className="palette-layer" onKeyDown={handleKeyDown}>
      <div className="palette-backdrop" aria-hidden="true" onClick={onClose} />
      <div className="palette" role="dialog" aria-modal="true" aria-label="Search the app">
        <div className="palette__search">
          <Search size={18} aria-hidden="true" />
          <input
            ref={inputRef}
            role="combobox"
            aria-expanded="true"
            aria-controls={listId}
            aria-activedescendant={activeItem ? `${listId}-${activeItem.id}` : undefined}
            aria-label="Search screens, leads, campaigns, products and templates"
            placeholder="Search or jump to…"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setActive(0);
            }}
          />
          <kbd>Esc</kbd>
        </div>
        <div className="palette__results" id={listId} role="listbox" aria-label="Results">
          {results.flat.length === 0 ? (
            <p className="palette__empty">Nothing matches “{query}”.</p>
          ) : (
            results.grouped.map((entry) => (
              <div key={entry.group} role="group" aria-label={entry.group}>
                <p className="palette__group" aria-hidden="true">{entry.group}</p>
                {entry.items.map((item) => {
                  const index = results.flat.indexOf(item);
                  return (
                    <div
                      key={item.id}
                      id={`${listId}-${item.id}`}
                      role="option"
                      aria-selected={index === active}
                      className={`palette__option${index === active ? " palette__option--active" : ""}`}
                      onMouseEnter={() => setActive(index)}
                      onClick={() => choose(item)}
                    >
                      <span>{item.label}</span>
                      {item.hint ? <small>{item.hint}</small> : null}
                      {index === active ? <CornerDownLeft size={14} aria-hidden="true" /> : null}
                    </div>
                  );
                })}
              </div>
            ))
          )}
        </div>
        <p className="palette__footer"><kbd>↑</kbd><kbd>↓</kbd> move · <kbd>Enter</kbd> open · <kbd>Esc</kbd> close</p>
      </div>
    </div>
  );
}
