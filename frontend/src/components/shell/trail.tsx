"use client";

import { usePathname } from "next/navigation";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { canSee } from "@/lib/permissions";
import type { PlatformDefinition, PlatformNavItem } from "@/platforms/types";
import { useActivePlatform } from "./active-platform";
import { isPathActive } from "./nav-item";
import { useSession } from "./session-provider";
import { SETTINGS_NAV } from "./settings-nav";
import { m } from "@/i18n";

type RuntimeTitle = { path: string; page?: string; detail?: string; section?: string } | null;

const TitleContext = createContext<{ title: RuntimeTitle; setTitle: (title: RuntimeTitle) => void }>({ title: null, setTitle: () => {} });

export function PageTitleProvider({ children }: { children: ReactNode }) {
  const [title, setTitle] = useState<RuntimeTitle>(null);
  return <TitleContext.Provider value={{ title, setTitle }}>{children}</TitleContext.Provider>;
}

/**
 * Names the current page for the breadcrumb and the mobile context bar. `detail` is a record name (thread subject);
 * `page`/`section` are for routes that are not static nav links (a label, a mailbox).
 */
export function usePageTitle(title: { page?: string; detail?: string | null; section?: string } | string | null | undefined) {
  const pathname = usePathname();
  const { setTitle } = useContext(TitleContext);
  const value = typeof title === "string" ? { detail: title } : title;
  const page = value?.page, detail = value?.detail ?? undefined, section = value?.section;
  useEffect(() => {
    if (!page && !detail && !section) return;
    setTitle({ path: pathname, page, detail, section });
    return () => setTitle(null);
  }, [pathname, page, detail, section, setTitle]);
  useEffect(() => {
    const name = detail || page;
    if (name) document.title = `${name} · ${m.brand.name}`;
  }, [detail, page]);
}

export type Trail = {
  platform: PlatformDefinition;
  section: string;
  page: string;
  url: string;
  icon?: ReactNode;
  detail?: string;
  /** Static links of the same section (mobile context strip). */
  siblings: PlatformNavItem[];
};

const pretty = (label: string) => label.charAt(0) + label.slice(1).toLowerCase();

export function useTrail(): Trail | null {
  const pathname = usePathname();
  const platform = useActivePlatform();
  const { me } = useSession();
  const { title } = useContext(TitleContext);
  const runtime = title && title.path === pathname ? title : null;
  const sections = [
    ...platform.nav.filter((section) => Array.isArray(section.items)).map((section) => ({ label: section.label, items: section.items as PlatformNavItem[] })),
    { label: m.shell.settings, items: SETTINGS_NAV },
  ];
  let best: { section: string; item: PlatformNavItem; items: PlatformNavItem[] } | null = null;
  for (const section of sections)
    for (const item of section.items)
      if (item.url && isPathActive(item.url, pathname) && (!best || item.url.length > (best.item.url?.length ?? 0))) best = { section: section.label, item, items: section.items };
  const visible = (items: PlatformNavItem[]) => items.filter((item) => item.url && canSee(me?.permissions, item.permission));
  if (!best) {
    if (!runtime?.page) return null;
    return { platform, section: pretty(runtime.section ?? platform.name), page: runtime.page, url: pathname ?? "", detail: runtime.detail, siblings: [] };
  }
  const exact = (best.item.url ?? "").split("?")[0] === pathname;
  return {
    platform,
    section: pretty(runtime?.section ?? best.section),
    page: runtime?.page ?? best.item.title,
    url: best.item.url!.split("?")[0],
    icon: best.item.icon,
    detail: exact && !runtime?.detail ? undefined : runtime?.detail,
    siblings: visible(best.items),
  };
}
