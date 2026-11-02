import {
  FileText,
  GitBranch,
  LayoutDashboard,
  ListChecks,
  MailCheck,
  Megaphone,
  MoreHorizontal,
  PackageSearch,
  Settings,
  Users,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useRef } from "react";

import type { WorkspaceSection } from "../domain";

interface Tab {
  section: WorkspaceSection;
  label: string;
  icon: LucideIcon;
  badge?: number;
  badgeLabel?: string;
}

interface MoreItem {
  section: WorkspaceSection;
  label: string;
  icon: LucideIcon;
  note?: string;
}

const MORE_ITEMS: MoreItem[] = [
  { section: "campaigns", label: "Campaigns", icon: Megaphone },
  { section: "leads", label: "All leads", icon: Users },
  { section: "catalogue", label: "Catalogue", icon: PackageSearch, note: "View only" },
  { section: "templates", label: "Templates", icon: FileText, note: "View only" },
  { section: "settings", label: "Settings", icon: Settings },
];

const PHONE_TAB_SECTIONS: WorkspaceSection[] = ["overview", "shortlist", "pipeline", "drafts"];

interface PhoneTabBarProps {
  active: WorkspaceSection;
  onSelect: (section: WorkspaceSection) => void;
  moreOpen: boolean;
  onMore: () => void;
  shortlistBadge?: number;
  followUpBadge?: number;
  draftsBadge?: number;
}

/** The phone's bottom navigation: the daily work in four tabs, everything else under More. */
export function PhoneTabBar({
  active,
  onSelect,
  moreOpen,
  onMore,
  shortlistBadge,
  followUpBadge,
  draftsBadge,
}: PhoneTabBarProps) {
  const tabs: Tab[] = [
    { section: "overview", label: "Today", icon: LayoutDashboard },
    { section: "shortlist", label: "Shortlist", icon: ListChecks, badge: shortlistBadge, badgeLabel: "awaiting a decision" },
    { section: "pipeline", label: "Pipeline", icon: GitBranch, badge: followUpBadge, badgeLabel: "follow-ups due" },
    { section: "drafts", label: "Drafts", icon: MailCheck, badge: draftsBadge, badgeLabel: "awaiting approval" },
  ];
  const moreActive = !PHONE_TAB_SECTIONS.includes(active);
  return (
    <nav className="phone-tabs" aria-label="Workspace navigation">
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const current = active === tab.section;
        return (
          <button
            key={tab.section}
            type="button"
            className="phone-tabs__item"
            aria-current={current ? "page" : undefined}
            onClick={() => onSelect(tab.section)}
          >
            <span className="phone-tabs__icon">
              <Icon size={21} aria-hidden="true" />
              {tab.badge ? (
                <span className="phone-tabs__badge" aria-label={`${tab.badge} ${tab.badgeLabel}`}>
                  {tab.badge > 99 ? "99+" : tab.badge}
                </span>
              ) : null}
            </span>
            <span>{tab.label}</span>
          </button>
        );
      })}
      <button
        type="button"
        className="phone-tabs__item"
        aria-current={moreActive ? "page" : undefined}
        aria-expanded={moreOpen}
        aria-controls="phone-more-sheet"
        onClick={onMore}
      >
        <span className="phone-tabs__icon"><MoreHorizontal size={21} aria-hidden="true" /></span>
        <span>More</span>
      </button>
    </nav>
  );
}

interface PhoneMoreSheetProps {
  active: WorkspaceSection;
  onSelect: (section: WorkspaceSection) => void;
  onClose: () => void;
}

/** Everything that isn't daily work, one tap from any screen. Esc or the backdrop closes it. */
export function PhoneMoreSheet({ active, onSelect, onClose }: PhoneMoreSheetProps) {
  const firstItem = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    firstItem.current?.focus();
    function onKey(event: KeyboardEvent): void {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      previous?.focus();
    };
  }, [onClose]);

  return (
    <div className="phone-sheet" role="presentation">
      <button type="button" className="phone-sheet__backdrop" aria-label="Close menu" onClick={onClose} />
      <div id="phone-more-sheet" className="phone-sheet__panel" role="dialog" aria-modal="true" aria-label="More">
        <span className="phone-sheet__grab" aria-hidden="true" />
        <ul>
          {MORE_ITEMS.map((item, index) => {
            const Icon = item.icon;
            return (
              <li key={item.section}>
                <button
                  ref={index === 0 ? firstItem : undefined}
                  type="button"
                  aria-current={active === item.section ? "page" : undefined}
                  onClick={() => {
                    onSelect(item.section);
                    onClose();
                  }}
                >
                  <Icon size={19} aria-hidden="true" />
                  <span>{item.label}</span>
                  {item.note ? <small>{item.note}</small> : null}
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
