import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Inbox,
  Info,
  LoaderCircle,
  MoreHorizontal,
  Trash2,
  X,
  type LucideIcon,
} from "lucide-react";
import {
  type KeyboardEvent,
  type ReactNode,
  useEffect,
  useId,
  useRef,
  useState,
} from "react";

import { PAGE_SIZE_OPTIONS } from "../pagination";
import { useRememberedState } from "../remembered";

export type HealthState = "checking" | "connected" | "unavailable";

interface ConnectionBadgeProps {
  state: HealthState;
}

const connectionLabels: Record<HealthState, string> = {
  checking: "Connecting to service",
  connected: "Service connected",
  unavailable: "Service offline",
};

/** A quiet dot while the local service is healthy; an explicit label when it is not. */
export function ConnectionBadge({ state }: ConnectionBadgeProps) {
  const label = connectionLabels[state];
  return (
    <div
      className={`connection-status connection-status--${state}`}
      role="status"
      aria-live="polite"
      title={label}
    >
      <span className="connection-status__dot" aria-hidden="true" />
      <span className={state === "connected" ? "visually-hidden" : undefined}>{label}</span>
    </div>
  );
}

interface NavigationItemProps {
  href: string;
  icon: LucideIcon;
  label: string;
  /** Work waiting for the operator; hidden when zero. */
  badge?: number;
  /** What the badge counts, read out with it, e.g. "need review". */
  badgeLabel?: string;
  active?: boolean;
  /** Icon-only sidebar: the label becomes a tooltip. */
  collapsed?: boolean;
  onSelect: () => void;
}

export function NavigationItem({
  href,
  icon: Icon,
  label,
  badge,
  badgeLabel,
  active = false,
  collapsed = false,
  onSelect,
}: NavigationItemProps) {
  const showBadge = badge !== undefined && badge > 0;
  const badgeText = showBadge ? `${badge}${badgeLabel ? ` ${badgeLabel}` : ""}` : "";
  return (
    <a
      className={`navigation-item${active ? " navigation-item--active" : ""}`}
      href={href}
      aria-current={active ? "location" : undefined}
      title={collapsed ? (showBadge ? `${label} · ${badgeText}` : label) : undefined}
      onClick={(event) => {
        event.preventDefault();
        onSelect();
      }}
    >
      <Icon size={20} aria-hidden="true" />
      <span className="navigation-item__label">{label}</span>
      {showBadge ? (
        <span className="navigation-badge">
          <span aria-hidden="true">{badge > 99 ? "99+" : badge}</span>
          <span className="visually-hidden">{badgeText}</span>
        </span>
      ) : null}
    </a>
  );
}

export interface TaskTabItem {
  id: string;
  label: string;
  count?: number;
}

interface TaskTabsProps {
  id: string;
  label: string;
  items: TaskTabItem[];
  activeId: string;
  onChange: (id: string) => void;
}

export function TaskTabs({ id, label, items, activeId, onChange }: TaskTabsProps) {
  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>): void {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const currentIndex = items.findIndex((item) => item.id === activeId);
    let nextIndex = currentIndex;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = items.length - 1;
    if (event.key === "ArrowLeft") {
      nextIndex = currentIndex <= 0 ? items.length - 1 : currentIndex - 1;
    }
    if (event.key === "ArrowRight") {
      nextIndex = currentIndex >= items.length - 1 ? 0 : currentIndex + 1;
    }
    const nextItem = items[nextIndex];
    if (!nextItem) return;
    onChange(nextItem.id);
    const buttons = event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>(
      '[role="tab"]',
    );
    buttons?.[nextIndex]?.focus();
  }

  return (
    <div className="task-tabs" role="tablist" aria-label={label}>
      {items.map((item) => {
        const selected = item.id === activeId;
        return (
          <button
            key={item.id}
            id={`${id}-tab-${item.id}`}
            className={`task-tab${selected ? " task-tab--active" : ""}`}
            type="button"
            role="tab"
            aria-selected={selected}
            aria-controls={`${id}-panel-${item.id}`}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(item.id)}
            onKeyDown={handleKeyDown}
          >
            <span>{item.label}</span>
            {item.count === undefined ? null : <span className="task-tab__count">{item.count}</span>}
          </button>
        );
      })}
    </div>
  );
}

interface TaskPanelProps {
  id: string;
  tabId: string;
  children: ReactNode;
  className?: string;
}

export function TaskPanel({ id, tabId, children, className = "" }: TaskPanelProps) {
  return (
    <div
      id={`${id}-panel-${tabId}`}
      className={`task-panel${className ? ` ${className}` : ""}`}
      role="tabpanel"
      aria-labelledby={`${id}-tab-${tabId}`}
      tabIndex={0}
    >
      {children}
    </div>
  );
}

interface PageHeaderProps {
  title: string;
  /** One sentence at most. */
  description?: ReactNode;
  action?: ReactNode;
}

export function PageHeader({ title, description, action }: PageHeaderProps) {
  return (
    <section className="page-intro" aria-labelledby="page-title">
      <div>
        <h1 id="page-title">{title}</h1>
        {description ? <p>{description}</p> : null}
      </div>
      {action}
    </section>
  );
}

interface SectionHeadingProps {
  id: string;
  title: string;
  description?: string;
  icon: LucideIcon;
  count?: number;
  actions?: ReactNode;
}

export function SectionHeading({
  id,
  title,
  description,
  icon: Icon,
  count,
  actions,
}: SectionHeadingProps) {
  return (
    <div className="section-heading">
      <div className="section-heading__icon" aria-hidden="true">
        <Icon size={20} />
      </div>
      <div className="section-heading__copy">
        <h2 id={id}>{title}</h2>
        {description ? <p>{description}</p> : null}
      </div>
      {count === undefined ? null : <span className="count-badge">{count}</span>}
      {actions ? <div className="section-heading__actions">{actions}</div> : null}
    </div>
  );
}

interface MetricCardProps {
  label: string;
  value: string | number;
  detail: string;
  icon: LucideIcon;
  tone?: "default" | "warning";
  onSelect?: () => void;
}

export function MetricCard({
  label,
  value,
  detail,
  icon: Icon,
  tone = "default",
  onSelect,
}: MetricCardProps) {
  const Root = onSelect ? "button" : "article";
  return (
    <Root
      className={`metric-card metric-card--${tone}${onSelect ? " metric-card--interactive" : ""}`}
      type={onSelect ? "button" : undefined}
      onClick={onSelect}
    >
      <div className="metric-card__icon" aria-hidden="true">
        <Icon size={18} />
      </div>
      <div>
        <p>{label}</p>
        <strong>{value}</strong>
        <small>{detail}</small>
      </div>
    </Root>
  );
}

interface EmptyStateProps {
  title: string;
  description: string;
  action?: ReactNode;
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <span className="empty-state__icon" aria-hidden="true">
        <Inbox size={22} />
      </span>
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}

interface LoadingStateProps {
  label: string;
}

export function LoadingState({ label }: LoadingStateProps) {
  return (
    <div className="loading-state" role="status">
      <LoaderCircle className="spin" size={20} aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

interface HelpTipProps {
  label: string;
  children: ReactNode;
}

export function HelpTip({ label, children }: HelpTipProps) {
  const tooltipId = useId();
  return (
    <span className="help-tip">
      <button
        className="help-tip__trigger"
        type="button"
        aria-label={label}
        aria-describedby={tooltipId}
      >
        <CircleHelp size={15} aria-hidden="true" />
      </button>
      <span className="help-tip__content" id={tooltipId} role="tooltip">
        {children}
      </span>
    </span>
  );
}

interface GuidanceNoteProps {
  title: string;
  children: ReactNode;
}

export function GuidanceNote({ title, children }: GuidanceNoteProps) {
  return (
    <div className="guidance-note">
      <Info size={18} aria-hidden="true" />
      <div>
        <strong>{title}</strong>
        <p>{children}</p>
      </div>
    </div>
  );
}

export interface StatItem {
  label: string;
  value: ReactNode;
  wide?: boolean;
}

interface StatGridProps {
  items: StatItem[];
  className: string;
  wideClassName?: string;
}

export function StatGrid({ items, className, wideClassName }: StatGridProps) {
  return (
    <dl className={className}>
      {items.map((item) => (
        <div key={item.label} className={item.wide ? wideClassName : undefined}>
          <dt>{item.label}</dt>
          <dd>{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}

interface DangerConfirmProps {
  intensity: "two-step" | "type-to-confirm";
  label: string;
  confirmingLabel?: string;
  confirmText?: string;
  confirmPlaceholder?: string;
  onConfirm: () => void;
  disabled?: boolean;
}

export function DangerConfirm({
  intensity,
  label,
  confirmingLabel = "Confirm delete",
  confirmText = "DELETE",
  confirmPlaceholder,
  onConfirm,
  disabled = false,
}: DangerConfirmProps) {
  const [armed, setArmed] = useState(false);
  const [typedValue, setTypedValue] = useState("");

  if (intensity === "type-to-confirm") {
    return (
      <div className="deletion-control">
        <label>
          <span className="visually-hidden">Type {confirmText} to confirm</span>
          <input
            value={typedValue}
            onChange={(event) => setTypedValue(event.target.value)}
            placeholder={confirmPlaceholder ?? `Type ${confirmText}`}
          />
        </label>
        <button
          className="danger-action"
          type="button"
          disabled={disabled || typedValue !== confirmText}
          onClick={onConfirm}
        >
          <Trash2 size={16} aria-hidden="true" /> {label}
        </button>
      </div>
    );
  }

  return (
    <button
      className="danger-action"
      type="button"
      disabled={disabled}
      onClick={() => {
        if (!armed) {
          setArmed(true);
          return;
        }
        setArmed(false);
        onConfirm();
      }}
    >
      <Trash2 size={16} aria-hidden="true" />
      {armed ? confirmingLabel : label}
    </button>
  );
}

interface PaginationProps {
  page: number;
  pageCount: number;
  pageSize: number;
  totalItems: number;
  itemLabel: string;
  onPageChange: (page: number) => void;
  compact?: boolean;
  /** Shows a rows-per-page choice when given. */
  onPageSizeChange?: (size: number) => void;
}

type PageToken = number | "ellipsis-left" | "ellipsis-right";

function pageTokens(page: number, pageCount: number): PageToken[] {
  if (pageCount <= 7) return Array.from({ length: pageCount }, (_, index) => index + 1);
  if (page <= 4) return [1, 2, 3, 4, 5, "ellipsis-right", pageCount];
  if (page >= pageCount - 3) {
    return [
      1,
      "ellipsis-left",
      pageCount - 4,
      pageCount - 3,
      pageCount - 2,
      pageCount - 1,
      pageCount,
    ];
  }
  return [1, "ellipsis-left", page - 1, page, page + 1, "ellipsis-right", pageCount];
}

export function Pagination({
  page,
  pageCount,
  pageSize,
  totalItems,
  itemLabel,
  onPageChange,
  compact = false,
  onPageSizeChange,
}: PaginationProps) {
  const smallestPageSize = onPageSizeChange ? Math.min(...PAGE_SIZE_OPTIONS) : pageSize;
  if (totalItems <= Math.min(pageSize, smallestPageSize)) return null;
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, totalItems);

  return (
    <nav className={`pagination${compact ? " pagination--compact" : ""}`} aria-label={`${itemLabel} pagination`}>
      <p className="pagination__summary" aria-live="polite">
        Showing {start}–{end} of {totalItems} {itemLabel}
      </p>
      <div className="pagination__controls">
        {onPageSizeChange ? (
          <label className="pagination__size">
            <span>Rows</span>
            <select
              value={pageSize}
              aria-label={`${itemLabel} per page`}
              onChange={(event) => onPageSizeChange(Number(event.target.value))}
            >
              {PAGE_SIZE_OPTIONS.map((size) => (
                <option key={size} value={size}>{size}</option>
              ))}
            </select>
          </label>
        ) : null}
        <button
          type="button"
          className="pagination__button pagination__button--direction"
          disabled={page === 1}
          onClick={() => onPageChange(page - 1)}
          aria-label={`Previous ${itemLabel} page`}
        >
          <ChevronLeft size={16} aria-hidden="true" />
          <span>Previous</span>
        </button>
        {compact ? (
          <span className="pagination__page-status">Page {page} of {pageCount}</span>
        ) : (
          pageTokens(page, pageCount).map((token) =>
            typeof token === "number" ? (
              <button
                type="button"
                className="pagination__button"
                key={token}
                aria-current={token === page ? "page" : undefined}
                aria-label={`Go to ${itemLabel} page ${token}`}
                onClick={() => onPageChange(token)}
              >
                {token}
              </button>
            ) : (
              <span className="pagination__ellipsis" aria-hidden="true" key={token}>…</span>
            ),
          )
        )}
        <button
          type="button"
          className="pagination__button pagination__button--direction"
          disabled={page === pageCount}
          onClick={() => onPageChange(page + 1)}
          aria-label={`Next ${itemLabel} page`}
        >
          <span>Next</span>
          <ChevronRight size={16} aria-hidden="true" />
        </button>
      </div>
    </nav>
  );
}

export type StatusTone = "neutral" | "success" | "warning" | "error" | "accent";

interface StatusPillProps {
  tone?: StatusTone;
  children: ReactNode;
}

/** One shape for every status; the dot and colour carry the meaning. */
export function StatusPill({ tone = "neutral", children }: StatusPillProps) {
  return <span className={`status-pill status-pill--${tone}`}>{children}</span>;
}

interface CollapsibleProps {
  /** Remembers whether the section is open, per screen, for the session. */
  rememberKey?: string;
  title: ReactNode;
  /** Shown beside the title while the section is collapsed, e.g. "3 notes". */
  summary?: ReactNode;
  icon?: LucideIcon;
  actions?: ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
  className?: string;
}

/** A section that expands and collapses, the same way on every screen. */
export function Collapsible({
  rememberKey,
  title,
  summary,
  icon: Icon,
  actions,
  defaultOpen = true,
  children,
  className = "",
}: CollapsibleProps) {
  const [open, setOpen] = useRememberedState(
    rememberKey ? `collapsible:${rememberKey}` : undefined,
    defaultOpen,
  );
  const bodyId = useId();
  return (
    <section className={`collapsible${open ? " collapsible--open" : ""}${className ? ` ${className}` : ""}`}>
      <div className="collapsible__header">
        <button
          type="button"
          className="collapsible__toggle"
          aria-expanded={open}
          aria-controls={bodyId}
          onClick={() => setOpen((current) => !current)}
        >
          <ChevronDown className="collapsible__chevron" size={18} aria-hidden="true" />
          {Icon ? <Icon size={18} aria-hidden="true" /> : null}
          <span className="collapsible__title">{title}</span>
          {!open && summary ? <span className="collapsible__summary">{summary}</span> : null}
        </button>
        {actions ? <div className="collapsible__actions">{actions}</div> : null}
      </div>
      <div className="collapsible__body" id={bodyId} hidden={!open}>
        <div className="collapsible__content">{children}</div>
      </div>
    </section>
  );
}

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

interface DrawerProps {
  open: boolean;
  title: string;
  description?: ReactNode;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}

/** A panel that slides in from the right for editing and previews. */
export function Drawer({ open, title, description, onClose, children, footer, wide = false }: DrawerProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const titleId = useId();

  useEffect(() => {
    if (!open) return;
    const returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    panelRef.current?.querySelector<HTMLElement>(FOCUSABLE)?.focus();
    return () => returnFocus?.focus();
  }, [open]);

  if (!open) return null;

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>): void {
    if (event.key === "Escape") {
      event.stopPropagation();
      onClose();
      return;
    }
    if (event.key !== "Tab" || !panelRef.current) return;
    const focusable = [...panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE)];
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (!first || !last) return;
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return (
    <div className="drawer-layer">
      <div className="drawer-backdrop" aria-hidden="true" onClick={onClose} />
      <div
        ref={panelRef}
        className={`drawer${wide ? " drawer--wide" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onKeyDown={handleKeyDown}
      >
        <header className="drawer__header">
          <div>
            <h2 id={titleId}>{title}</h2>
            {description ? <p>{description}</p> : null}
          </div>
          <button type="button" className="icon-button" aria-label={`Close ${title}`} title="Close" onClick={onClose}>
            <X size={18} aria-hidden="true" />
          </button>
        </header>
        <div className="drawer__body">{children}</div>
        {footer ? <footer className="drawer__footer">{footer}</footer> : null}
      </div>
    </div>
  );
}

interface FilterChipProps {
  label: string;
  onRemove: () => void;
}

/** An active filter, removable in one click. */
export function FilterChip({ label, onRemove }: FilterChipProps) {
  return (
    <span className="filter-chip">
      {label}
      <button type="button" aria-label={`Remove filter ${label}`} onClick={onRemove}>
        <X size={14} aria-hidden="true" />
      </button>
    </span>
  );
}

interface ToolbarProps {
  children: ReactNode;
  /** Active filters as chips, with a "Clear all" control. */
  chips?: { label: string; onRemove: () => void }[];
  onClearAll?: () => void;
  summary?: ReactNode;
}

/** Search, filters and a result count, sticking below the page header while scrolling. */
export function Toolbar({ children, chips = [], onClearAll, summary }: ToolbarProps) {
  return (
    <div className="toolbar">
      <div className="toolbar__controls">{children}</div>
      {chips.length > 0 || summary ? (
        <div className="toolbar__status">
          {chips.length > 0 ? (
            <div className="toolbar__chips" aria-label="Active filters">
              {chips.map((chip) => (
                <FilterChip key={chip.label} label={chip.label} onRemove={chip.onRemove} />
              ))}
              {onClearAll ? (
                <button type="button" className="toolbar__clear" onClick={onClearAll}>
                  Clear all
                </button>
              ) : null}
            </div>
          ) : null}
          {summary ? <p className="toolbar__summary" aria-live="polite">{summary}</p> : null}
        </div>
      ) : null}
    </div>
  );
}

interface SkeletonRowsProps {
  rows?: number;
  label: string;
}

/** Placeholder rows shaped like real ones, so the page does not jump when data arrives. */
export function SkeletonRows({ rows = 5, label }: SkeletonRowsProps) {
  return (
    <div className="skeleton-rows" role="status" aria-label={label}>
      {Array.from({ length: rows }, (_, index) => (
        <div className="skeleton-row" key={index} aria-hidden="true">
          <span className="skeleton-block skeleton-block--title" />
          <span className="skeleton-block" />
          <span className="skeleton-block skeleton-block--short" />
        </div>
      ))}
    </div>
  );
}

interface MoreMenuProps {
  /** Accessible name of the trigger, e.g. "More actions for Luton Bakeries". */
  label: string;
  children: ReactNode;
}

/** Secondary actions behind one button. Closes on Escape, on a click outside, and after an action. */
export function MoreMenu({ label, children }: MoreMenuProps) {
  const menuRef = useRef<HTMLDetailsElement>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    function close(event: Event): void {
      if (event instanceof KeyboardEvent ? event.key === "Escape" : !menuRef.current?.contains(event.target as Node)) {
        setOpen(false);
        if (event instanceof KeyboardEvent) menuRef.current?.querySelector("summary")?.focus();
      }
    }
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("pointerdown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  return (
    <details
      ref={menuRef}
      className="more-menu"
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary className="tertiary-action" aria-label={label}>
        <MoreHorizontal size={16} aria-hidden="true" /> More
      </summary>
      <div className="more-menu__items" onClick={() => setOpen(false)}>
        {children}
      </div>
    </details>
  );
}
