"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
import { cn } from "@/utils/cn";
import { useActivePlatform } from "./active-platform";
import { useTrail } from "./trail";

function NoBadges(): Record<string, number> { return {}; }

/**
 * Below `xl`: where am I? Line 1 is the platform's context switcher (Gmail: mailbox) and `Section | Page · detail`;
 * line 2 is a swipeable strip of the section's sibling pages with badges.
 */
export function ContextBar({ onSectionClick }: { onSectionClick?: () => void }) {
  const trail = useTrail();
  const platform = useActivePlatform();
  const badges = (platform.useBadges ?? NoBadges)();
  const strip = useRef<HTMLDivElement>(null);
  const { ContextSwitcher } = platform;

  const activeUrl = trail?.url;
  useEffect(() => {
    const box = strip.current;
    const active = box?.querySelector<HTMLElement>('[aria-current="page"]');
    if (!box || !active) return;
    box.scrollTo({ left: Math.max(0, active.offsetLeft - (box.clientWidth - active.offsetWidth) / 2), behavior: "instant" as ScrollBehavior });
  }, [activeUrl]);

  if (!trail && !ContextSwitcher) return null;
  return (
    <div className="mt-2 border-t border-card-border pt-2 xl:hidden" data-context-bar="">
      <div className="flex min-h-9 min-w-0 items-center gap-2 px-1 text-sm">
        {ContextSwitcher && <div className="w-[min(46%,13rem)] shrink-0"><ContextSwitcher compact /></div>}
        {trail && (
          <nav aria-label="You are here" className="min-w-0 flex-1">
            <ol className="flex min-w-0 items-center gap-2">
              <li className="shrink-0">
                <button type="button" onClick={onSectionClick} aria-label={`${trail.section}: show menu`}
                  className="rounded-md py-1 text-text-secondary underline-offset-4 hover:text-text-primary hover:underline focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none">
                  {trail.section}
                </button>
              </li>
              <li aria-hidden="true" className="h-4 w-px shrink-0 bg-card-border" />
              <li className="min-w-0 truncate">
                {trail.detail ? (
                  <><Link href={trail.url} className="font-semibold text-text-primary hover:underline">{trail.page}</Link><span className="text-text-tertiary"> › </span><span aria-current="page" className="text-text-secondary">{trail.detail}</span></>
                ) : (
                  <span aria-current="page" className="font-semibold text-text-primary">{trail.page}</span>
                )}
              </li>
            </ol>
          </nav>
        )}
      </div>

      {trail && trail.siblings.length > 1 && (
        <div className="relative -mx-2 mt-1.5">
          <div ref={strip} role="navigation" aria-label={`${trail.section} pages`}
            className="flex snap-x snap-mandatory gap-1.5 overflow-x-auto px-2 pb-0.5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden [mask-image:linear-gradient(to_right,transparent,black_12px,black_calc(100%-16px),transparent)]">
            {trail.siblings.map((item) => {
              const active = item.url === trail.url;
              const badge = item.badgeKey ? badges[item.badgeKey] : 0;
              return (
                <Link key={item.url} href={item.url!} aria-current={active ? "page" : undefined}
                  className={cn(
                    "relative inline-flex h-10 shrink-0 snap-start items-center gap-1.5 rounded-lg px-3 text-sm font-medium whitespace-nowrap transition-colors focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none",
                    active ? "bg-primary-500/10 text-primary-600 after:absolute after:inset-x-2 after:bottom-0 after:h-0.5 after:rounded-full after:bg-primary-500 dark:text-primary-300" : "text-text-secondary hover:bg-background-gray-secondary_alt hover:text-text-primary",
                  )}>
                  {item.title}
                  {badge ? <span className="rounded-full bg-primary-500/10 px-1.5 text-xs text-primary-600 tabular-nums dark:text-primary-300">{badge > 99 ? "99+" : badge}<span className="sr-only"> unread</span></span> : null}
                </Link>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
