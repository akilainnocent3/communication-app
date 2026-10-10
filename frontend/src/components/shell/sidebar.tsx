"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useSession } from "@/components/shell/session-provider";
import { CloseIcon, DotsIcon, LogoutIcon, SearchIcon, SplitIcon } from "@/components/ui/icons";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/tailgrids/core/tooltip";
import { m } from "@/i18n";
import { initials } from "@/lib/format";
import { canSee } from "@/lib/permissions";
import type { PlatformNavItem, PlatformNavSection } from "@/platforms/types";
import { errorMessage } from "@/services/api/client";
import { cn } from "@/utils/cn";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useActivePlatform } from "./active-platform";
import { BrandLogo, BrandMark } from "./brand";
import { NavItem } from "./nav-item";
import { SETTINGS_NAV } from "./settings-nav";

type Props = { isSidebarOpen: boolean; toggleSidebar: () => void; isMobileSheet?: boolean; onItemClick?: () => void };

function SectionLabel({ label, collapsed }: { label: string; collapsed: boolean }) {
  if (collapsed) return <span aria-hidden="true" className="flex items-center justify-center pt-4 pb-2 text-icon-secondary"><DotsIcon size={16} /></span>;
  return (
    <p className="mt-5 mb-1.5 flex items-center gap-2 px-3 text-[11px] font-semibold tracking-[0.08em] text-text-tertiary uppercase before:mr-1 before:h-px before:w-3 before:bg-card-border after:h-px after:flex-1 after:bg-card-border">
      {label}
    </p>
  );
}

function Section({ label, items, collapsed, mobile, needle, badges, onNavigate }: {
  label: string; items: PlatformNavItem[]; collapsed: boolean; mobile: boolean; needle: string; badges: Record<string, number>; onNavigate?: () => void;
}) {
  const { me } = useSession();
  const visible = items
    .filter((item) => item.url && canSee(me?.permissions, item.permission))
    .filter((item) => !needle || `${label} ${item.title}`.toLowerCase().includes(needle));
  if (!visible.length) return null;
  return (
    <div>
      <SectionLabel label={label} collapsed={collapsed} />
      <div className={cn("space-y-0.5", collapsed && "space-y-1.5")}>
        {visible.map((item) => (
          <NavItem key={item.url} href={item.url!} icon={item.icon} label={item.title} dot={item.dot} badge={item.badgeKey ? badges[item.badgeKey] : undefined} collapsed={collapsed} mobile={mobile} onNavigate={onNavigate} />
        ))}
      </div>
    </div>
  );
}

/** Sections whose items come from a hook (e.g. labels) render through this so the hook runs inside a component. */
function DynamicSection({ section, ...rest }: Omit<React.ComponentProps<typeof Section>, "items" | "label"> & { section: PlatformNavSection }) {
  const items = (section.items as () => PlatformNavItem[])();
  return <Section label={section.label} items={items} {...rest} />;
}

function NoBadges(): Record<string, number> { return {}; }

export default function Sidebar({ isSidebarOpen, toggleSidebar, isMobileSheet = false, onItemClick }: Props) {
  const platform = useActivePlatform();
  const badges = (platform.useBadges ?? NoBadges)();
  const [search, setSearch] = useState("");
  const needle = search.trim().toLowerCase();
  const collapsed = !isSidebarOpen;
  const navRef = useRef<HTMLElement>(null);
  const onNavigate = () => { setSearch(""); onItemClick?.(); };
  const { ContextSwitcher, SidebarAction } = platform;

  useEffect(() => {
    if (!isMobileSheet) return;
    const frame = window.requestAnimationFrame(() => navRef.current?.querySelector('[aria-current="page"]')?.scrollIntoView({ block: "center" }));
    return () => window.cancelAnimationFrame(frame);
  }, [isMobileSheet]);

  const shared = { collapsed, mobile: isMobileSheet, needle, badges, onNavigate };

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className={cn("flex items-center px-4 pt-6 text-text-primary", isSidebarOpen ? "justify-between" : "flex-col justify-center gap-4")}>
        <Link href="/" aria-label={m.shell.home} className="rounded-lg focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none">
          {isSidebarOpen ? <BrandLogo /> : <BrandMark />}
        </Link>
        <button
          type="button"
          onClick={toggleSidebar}
          aria-label={isMobileSheet ? m.shell.closeMenu : m.shell.toggleSidebar}
          className="flex size-10 items-center justify-center rounded-lg text-icon-tertiary transition-colors hover:bg-background-gray-secondary_alt hover:text-text-primary focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none"
        >
          {isMobileSheet ? <CloseIcon /> : <SplitIcon />}
        </button>
      </div>

      {(ContextSwitcher || SidebarAction) && (
        <div className={cn("space-y-3", isSidebarOpen ? "px-4 pt-5" : "flex flex-col items-center px-2 pt-4")}>
          {ContextSwitcher && <ContextSwitcher collapsed={collapsed} />}
          {SidebarAction && <SidebarAction collapsed={collapsed} onAction={onItemClick} />}
        </div>
      )}

      {isMobileSheet && (
        <div className="px-4 pt-4">
          <label className="relative block">
            <span className="sr-only">{m.shell.searchMenu}</span>
            <SearchIcon className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-icon-tertiary" />
            <input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder={m.shell.searchMenu}
              className="h-11 w-full rounded-lg border border-card-border bg-card-surface-area pr-3 pl-9 text-sm text-text-primary placeholder:text-text-tertiary focus:border-primary-500 focus:ring-2 focus:ring-primary-500/30 focus:outline-none" />
          </label>
        </div>
      )}

      <nav ref={navRef} aria-label={`${platform.name} navigation`} className={cn("scrollbar-thin flex-1 overflow-y-auto", isSidebarOpen ? "mt-1 px-4 pb-4" : "mt-2 px-2 pb-4")}>
        {platform.nav.map((section) =>
          typeof section.items === "function"
            ? <DynamicSection key={section.label} section={section} {...shared} />
            : <Section key={section.label} label={section.label} items={section.items} {...shared} />,
        )}
        <Section label={m.shell.settings} items={SETTINGS_NAV} {...shared} />
      </nav>

      <SidebarAccount collapsed={collapsed} />
    </div>
  );
}

function SidebarAccount({ collapsed }: { collapsed: boolean }) {
  const session = useSession();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  if (!session.me) return null;
  const name = session.me.user.display_name;
  const role = session.me.role?.name ?? "Staff";
  async function signOut() {
    setBusy(true);
    try { await session.signOut(); router.replace("/login"); } catch (error) { toast.error(errorMessage(error)); } finally { setBusy(false); }
  }
  const avatar = <span aria-hidden="true" className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary-500/15 text-sm font-semibold text-primary-600 dark:text-primary-300">{initials(name)}</span>;
  const button = (
    <button type="button" onClick={signOut} disabled={busy} aria-label={busy ? m.auth.signingOut : m.auth.signOut} title={m.auth.signOut}
      className="flex size-8 shrink-0 items-center justify-center rounded-lg text-icon-tertiary transition-colors hover:bg-background-gray-secondary_alt hover:text-error-500 focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none disabled:opacity-50">
      <LogoutIcon />
    </button>
  );
  if (collapsed)
    return (
      <div className="mt-auto flex flex-col items-center gap-2 border-t border-card-border px-2 py-3">
        <Tooltip placement="right">
          <TooltipTrigger asChild><span tabIndex={0} className="rounded-full focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none">{avatar}</span></TooltipTrigger>
          <TooltipContent><p>{name} · {role}</p></TooltipContent>
        </Tooltip>
        {button}
      </div>
    );
  return (
    <div className="mt-auto border-t border-card-border p-3">
      <div className="flex items-center gap-3 rounded-xl border border-card-border bg-background-gray-secondary_alt/40 p-2.5">
        {avatar}
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-text-primary" title={name}>{name}</span>
          <span className="block truncate text-xs text-text-tertiary">{role}</span>
        </span>
        {button}
      </div>
    </div>
  );
}
