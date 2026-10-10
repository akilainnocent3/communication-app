"use client";

import { usePathname } from "next/navigation";
import { Fragment, useRef, useState, type ReactNode } from "react";
import { SheetContent, SheetOverlay, SheetTitle } from "@/components/tailgrids/core/sheet";
import { readStored, writeStored } from "@/lib/storage";
import { cn } from "@/utils/cn";
import { useActivePlatform } from "./active-platform";
import Header from "./header";
import { MainScrollProvider } from "./main-scroll";
import { NavigationPending } from "./navigation-pending";
import { OfflineBanner } from "./offline-banner";
import Sidebar from "./sidebar";
import { PageTitleProvider } from "./trail";

const SIDEBAR_KEY = "cm:sidebar-open";

/** Admin shell: 270 ↔ 72 px collapsible sidebar (xl+), left sheet below xl, rounded content panel, sticky header. */
export function AppShell({ children }: { children: ReactNode }) {
  const [isSidebarOpen, setIsSidebarOpen] = useState(() => readStored(SIDEBAR_KEY, true));
  const [isMobileSheetOpen, setIsMobileSheetOpen] = useState(false);
  const pathname = usePathname();
  const [seenPath, setSeenPath] = useState(pathname);
  if (seenPath !== pathname) { setSeenPath(pathname); setIsMobileSheetOpen(false); }
  const mainRef = useRef<HTMLElement>(null);
  const platform = useActivePlatform();
  const PlatformProvider = platform.Provider ?? Fragment;
  const toggle = () => setIsSidebarOpen((open) => { writeStored(SIDEBAR_KEY, !open); return !open; });

  return (
    <PageTitleProvider>
      <PlatformProvider key={platform.key}>
        <NavigationPending />
        <div className="flex h-full">
          <aside
            style={{ width: isSidebarOpen ? 270 : 72, minWidth: isSidebarOpen ? 270 : 72, transition: "width 300ms cubic-bezier(0.4,0,0.2,1), min-width 300ms cubic-bezier(0.4,0,0.2,1)" }}
            className="hidden shrink-0 overflow-hidden xl:block"
          >
            <Sidebar isSidebarOpen={isSidebarOpen} toggleSidebar={toggle} />
          </aside>

          <SheetOverlay isOpen={isMobileSheetOpen} onOpenChange={setIsMobileSheetOpen}>
            <SheetContent side="left" showCloseButton={false} className="w-[min(20rem,85vw)]! max-w-[min(20rem,85vw)]! min-w-0! border-r border-card-border bg-card-surface-area p-0">
              <SheetTitle className="sr-only">Menu</SheetTitle>
              <Sidebar isSidebarOpen toggleSidebar={() => setIsMobileSheetOpen(false)} onItemClick={() => setIsMobileSheetOpen(false)} isMobileSheet />
            </SheetContent>
          </SheetOverlay>

          <div className={cn("min-w-0 flex-1", isSidebarOpen ? "lg:p-4 xl:pl-0" : "lg:py-4 xl:pr-4")}>
            <div className="flex h-full flex-col overflow-hidden border-[0.5px] border-card-surface-border bg-card-surface-area lg:rounded-2xl lg:shadow-[0_3px_6px_-2px_rgba(0,0,0,0.02),0_1px_1px_0_rgba(0,0,0,0.04)]">
              <MainScrollProvider target={mainRef}>
                <Header onMenuClick={() => setIsMobileSheetOpen(true)} />
                <OfflineBanner />
                <main ref={mainRef} id="main" className="scrollbar-thin relative flex min-h-0 flex-1 flex-col overflow-x-hidden overflow-y-auto">
                  {children}
                </main>
              </MainScrollProvider>
            </div>
          </div>
        </div>
      </PlatformProvider>
    </PageTitleProvider>
  );
}
