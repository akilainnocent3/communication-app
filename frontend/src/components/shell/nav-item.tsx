"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/tailgrids/core/tooltip";
import { cn } from "@/utils/cn";

export function isPathActive(href: string, pathname: string | null) {
  const path = href.split("?")[0];
  return !!pathname && (pathname === path || pathname.startsWith(`${path}/`));
}

function Badge({ count }: { count?: number }) {
  if (!count) return null;
  return (
    <span className="ml-auto rounded-full bg-primary-500/10 px-2 py-0.5 text-xs font-semibold text-primary-600 tabular-nums dark:text-primary-300">
      {count > 999 ? "999+" : count}
      <span className="sr-only"> unread</span>
    </span>
  );
}

/** One sidebar link: full row when expanded, an icon with a tooltip when the rail is collapsed. */
export function NavItem({ href, icon, label, badge, dot, collapsed, mobile, onNavigate }: {
  href: string; icon: React.ReactNode; label: string; badge?: number; dot?: string; collapsed?: boolean; mobile?: boolean; onNavigate?: () => void;
}) {
  const pathname = usePathname();
  const active = isPathActive(href, pathname);
  const glyph = dot ? <span aria-hidden="true" className="flex size-[18px] items-center justify-center"><span className="size-2.5 rounded-full" style={{ background: dot }} /></span> : icon;

  if (collapsed)
    return (
      <div className="flex justify-center">
        <Tooltip placement="right">
          <TooltipTrigger asChild>
            <Link
              href={href}
              onClick={onNavigate}
              aria-label={badge ? `${label} (${badge} unread)` : label}
              aria-current={active ? "page" : undefined}
              className={cn(
                "relative flex size-10 items-center justify-center rounded-lg focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none",
                active ? "bg-primary-500/10 text-primary-500 dark:text-primary-300" : "text-icon-tertiary transition-colors hover:bg-sidebar-navigation-nav-item-nav-hover-background hover:text-icon-primary",
              )}
            >
              {glyph}
              {badge ? <span aria-hidden="true" className="absolute top-1.5 right-1.5 size-2 rounded-full bg-primary-500 ring-2 ring-card-surface-area" /> : null}
            </Link>
          </TooltipTrigger>
          <TooltipContent><p>{label}{badge ? ` · ${badge}` : ""}</p></TooltipContent>
        </Tooltip>
      </div>
    );

  return (
    <Link
      href={href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        "relative flex min-h-9 w-full items-center gap-3 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none",
        mobile && "max-xl:min-h-11",
        active
          ? "bg-primary-500/10 text-primary-600 before:absolute before:inset-y-1.5 before:left-0 before:w-[3px] before:rounded-full before:bg-primary-500 dark:text-primary-300"
          : "text-text-secondary hover:bg-sidebar-navigation-nav-item-nav-hover-background hover:text-text-primary",
        badge && !active && "font-semibold text-text-primary",
      )}
    >
      <span className={active ? "text-primary-500 dark:text-primary-300" : "text-icon-tertiary"}>{glyph}</span>
      <span className="min-w-0 flex-1 truncate">{label}</span>
      <Badge count={badge} />
    </Link>
  );
}
