import {
  ChevronLeft,
  ChevronRight,
  CircleCheck,
  CircleDashed,
  CircleX,
  Inbox,
  LoaderCircle,
  Trash2,
  type LucideIcon,
} from "lucide-react";
import { type KeyboardEvent, type ReactNode, useState } from "react";

export type HealthState = "checking" | "connected" | "unavailable";

interface ConnectionBadgeProps {
  state: HealthState;
}

const connectionPresentation: Record<
  HealthState,
  { icon: LucideIcon; label: string; detail: string }
> = {
  checking: { icon: CircleDashed, label: "API checking", detail: "Local service" },
  connected: { icon: CircleCheck, label: "API connected", detail: "Local service" },
  unavailable: { icon: CircleX, label: "API unavailable", detail: "Action required" },
};

export function ConnectionBadge({ state }: ConnectionBadgeProps) {
  const presentation = connectionPresentation[state];
  const Icon = presentation.icon;
  return (
    <div className={`connection-badge connection-badge--${state}`} role="status" aria-live="polite">
      <Icon size={18} aria-hidden="true" />
      <span>
        <strong>{presentation.label}</strong>
        <small>{presentation.detail}</small>
      </span>
    </div>
  );
}

interface NavigationItemProps {
  href: string;
  icon: LucideIcon;
  label: string;
  count?: number;
  active?: boolean;
  onSelect: () => void;
}

export function NavigationItem({
  href,
  icon: Icon,
  label,
  count,
  active = false,
  onSelect,
}: NavigationItemProps) {
  return (
    <a
      className={`navigation-item${active ? " navigation-item--active" : ""}`}
      href={href}
      aria-current={active ? "location" : undefined}
      onClick={(event) => {
        event.preventDefault();
        onSelect();
      }}
    >
      <Icon size={20} aria-hidden="true" />
      <span>{label}</span>
      {count === undefined ? null : <span className="navigation-count">{count}</span>}
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
  eyebrow: string;
  title: string;
  description: ReactNode;
  action?: ReactNode;
}

export function PageHeader({ eyebrow, title, description, action }: PageHeaderProps) {
  return (
    <section className="page-intro" aria-labelledby="page-title">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1 id="page-title">{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </section>
  );
}

interface SectionHeadingProps {
  id: string;
  eyebrow: string;
  title: string;
  description: string;
  icon: LucideIcon;
  count?: number;
}

export function SectionHeading({
  id,
  eyebrow,
  title,
  description,
  icon: Icon,
  count,
}: SectionHeadingProps) {
  return (
    <div className="section-heading">
      <div className="section-heading__icon" aria-hidden="true">
        <Icon size={20} />
      </div>
      <div className="section-heading__copy">
        <p className="eyebrow">{eyebrow}</p>
        <h2 id={id}>{title}</h2>
        <p>{description}</p>
      </div>
      {count === undefined ? null : <span className="count-badge">{count}</span>}
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
}: PaginationProps) {
  if (totalItems <= pageSize) return null;
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, totalItems);

  return (
    <nav className={`pagination${compact ? " pagination--compact" : ""}`} aria-label={`${itemLabel} pagination`}>
      <p className="pagination__summary" aria-live="polite">
        Showing {start}–{end} of {totalItems} {itemLabel}
      </p>
      <div className="pagination__controls">
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
