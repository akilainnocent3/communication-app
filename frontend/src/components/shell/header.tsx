"use client";

import Link from "next/link";
import { useState } from "react";
import { ChevronRightIcon, DotsVerticalIcon, MenuIcon } from "@/components/ui/icons";
import { m } from "@/i18n";
import { cn } from "@/utils/cn";
import { BrandMark } from "./brand";
import { CommandPalette } from "./command-palette";
import { ContextBar } from "./context-bar";
import { useMainScrolled } from "./main-scroll";
import { PlatformSwitcher, PlatformSwitcherCompact } from "./platform-switcher";
import ThemeToggle from "./theme-toggle";
import { useTrail } from "./trail";
import { UserMenu } from "./user-menu";

function RouteBreadcrumb() {
  const trail = useTrail();
  if (!trail) return <p className="truncate text-sm font-medium text-text-secondary">{m.brand.name}</p>;
  return (
    <nav aria-label="Breadcrumb" className="min-w-0">
      <ol className="flex min-w-0 items-center gap-1.5 text-sm">
        <li className="flex shrink-0 items-center gap-2 text-text-tertiary">
          <span aria-hidden="true" className={cn("[&_svg]:size-4", trail.platform.accent)}>{trail.platform.icon}</span>
          <Link href={trail.platform.homePath} className="hover:text-text-primary hover:underline">{trail.platform.name}</Link>
        </li>
        <li aria-hidden="true" className="text-icon-tertiary"><ChevronRightIcon size={14} /></li>
        <li className="min-w-0 truncate">
          {trail.detail ? <Link href={trail.url} className="font-medium text-text-secondary hover:text-text-primary hover:underline">{trail.page}</Link> : <span aria-current="page" className="font-medium text-text-primary">{trail.page}</span>}
        </li>
        {trail.detail && (
          <>
            <li aria-hidden="true" className="text-icon-tertiary"><ChevronRightIcon size={14} /></li>
            <li className="min-w-0 truncate"><span aria-current="page" className="font-medium text-text-primary">{trail.detail}</span></li>
          </>
        )}
      </ol>
    </nav>
  );
}

/** Sticky blurred header (outside the scrolling main), shadow appears once the page scrolls. */
export default function Header({ onMenuClick }: { onMenuClick?: () => void }) {
  const [drawer, setDrawer] = useState(false);
  const scrolled = useMainScrolled();
  return (
    <>
      <header className={cn(
        "sticky top-0 z-40 w-full border-b-[0.5px] border-card-border bg-card-surface-area/85 px-2 pt-2 pb-1.5 backdrop-blur transition-shadow duration-200 supports-[backdrop-filter]:bg-card-surface-area/70 lg:px-5 xl:py-3",
        scrolled && "shadow-[0_6px_16px_-10px_rgba(0,0,0,0.25)]",
      )}>
        <div className="xl:hidden">
          <div className="flex items-center">
            <div className="flex flex-1 justify-start">
              <button id="mobile-menu-toggle" type="button" onClick={onMenuClick} aria-label={m.shell.openMenu}
                className="flex size-10 items-center justify-center rounded-lg text-icon-tertiary transition-colors hover:text-text-primary focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none">
                <MenuIcon />
              </button>
            </div>
            <Link href="/" aria-label={m.shell.home} className="rounded-lg focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none"><BrandMark size={28} /></Link>
            <div className="flex flex-1 justify-end">
              <button type="button" onClick={() => setDrawer(!drawer)} aria-label={m.shell.quickAccess} aria-expanded={drawer}
                className={cn("flex size-10 items-center justify-center rounded-lg transition-colors focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none", drawer ? "bg-background-gray-secondary text-text-primary" : "text-icon-tertiary hover:text-text-primary")}>
                <DotsVerticalIcon />
              </button>
            </div>
          </div>
          <div className="mt-2 flex min-h-9 justify-center"><PlatformSwitcherCompact className="max-w-xs" /></div>
          <ContextBar onSectionClick={onMenuClick} />
        </div>

        <div className="hidden min-h-10 grid-cols-[1fr_auto_1fr] items-center gap-4 xl:grid">
          <div className="min-w-0"><RouteBreadcrumb /></div>
          <div className="flex justify-center"><PlatformSwitcher /></div>
          <div className="flex items-center justify-end gap-2.5">
            <CommandPalette />
            <ThemeToggle />
            <UserMenu />
          </div>
        </div>
      </header>
      <div className={cn("xl:hidden", drawer ? "block animate-fade-in" : "hidden")}>
        <div className="flex items-center justify-between gap-2.5 border-b border-card-border px-4 py-3 shadow-xs">
          <div className="flex items-center gap-2.5"><ThemeToggle /><CommandPalette /></div>
          <UserMenu compact />
        </div>
      </div>
    </>
  );
}
