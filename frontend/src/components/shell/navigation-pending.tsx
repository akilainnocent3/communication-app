"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

/** Longest time the indicator may show; a cancelled or failed navigation can never leave it on. */
const SAFETY_TIMEOUT_MS = 10_000;
const NAVIGATE_EVENT = "cm:navigate";

/**
 * Programmatic navigations (react-aria menu items and links routed through `RouterProvider`, `router.push` after a
 * menu action) never fire a DOM click, so they announce themselves here to show the same progress bar.
 */
export function startNavigationPending(href: string) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(NAVIGATE_EVENT, { detail: href }));
}

/**
 * Immediate feedback for internal (SPA) navigation: a valid same-origin link click to another page shows the
 * thin top progress bar until the pathname changes. It only observes clicks — Next <Link> still performs the
 * navigation, so nothing reloads and Back/Forward are untouched. Modifier clicks, new tabs, downloads, external URLs,
 * hash-only and same-page links are ignored.
 */
export function NavigationPending() {
  const pathname = usePathname();
  const [pendingFrom, setPendingFrom] = useState<string | null>(null);
  const [seenPath, setSeenPath] = useState(pathname);
  if (seenPath !== pathname) {  // navigation finished: forget the pending click (React "adjust state on change" pattern)
    setSeenPath(pathname);
    setPendingFrom(null);
  }

  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const anchor = (event.target as Element | null)?.closest?.("a[href]") as HTMLAnchorElement | null;
      if (!anchor || anchor.hasAttribute("download") || (anchor.target && anchor.target !== "_self")) return;
      const url = new URL(anchor.href, window.location.href);
      if (url.origin !== window.location.origin || url.pathname === window.location.pathname) return;
      setPendingFrom(window.location.pathname);
    };
    const onNavigate = (event: Event) => {
      const href = (event as CustomEvent<string>).detail;
      const url = new URL(href, window.location.href);
      if (url.origin !== window.location.origin || url.pathname === window.location.pathname) return;
      setPendingFrom(window.location.pathname);
    };
    // Capture phase: Next <Link> calls preventDefault in its own (bubbling) handler, which would hide the click.
    document.addEventListener("click", onClick, true);
    window.addEventListener(NAVIGATE_EVENT, onNavigate);
    return () => {
      document.removeEventListener("click", onClick, true);
      window.removeEventListener(NAVIGATE_EVENT, onNavigate);
    };
  }, []);

  const pending = pendingFrom !== null && pendingFrom === pathname;
  useEffect(() => {
    if (!pending) return;
    const timer = window.setTimeout(() => setPendingFrom(null), SAFETY_TIMEOUT_MS);
    return () => window.clearTimeout(timer);
  }, [pending]);

  if (!pending) return null;
  // Thin indeterminate bar pinned to the very top (the top edge of the sticky header).
  return (
    <div role="progressbar" aria-label="Loading page" className="pointer-events-none fixed inset-x-0 top-0 z-[60] h-0.5 overflow-hidden bg-primary-500/15" data-navigation-pending="">
      <span className="block h-full w-full origin-left bg-primary-500 animate-progress" />
    </div>
  );
}
