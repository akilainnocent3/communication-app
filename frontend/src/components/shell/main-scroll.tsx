"use client";

import { createContext, useContext, useEffect, useState, type ReactNode, type RefObject } from "react";

const MainScrolled = createContext(false);

/** Tracks whether the page's scroll container (`main`) has scrolled, so the sticky header can lift its shadow. */
export function MainScrollProvider({ target, children }: { target: RefObject<HTMLElement | null>; children: ReactNode }) {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const element = target.current;
    if (!element) return;
    const onScroll = () => setScrolled(element.scrollTop > 4);
    onScroll();
    element.addEventListener("scroll", onScroll, { passive: true });
    return () => element.removeEventListener("scroll", onScroll);
  }, [target]);
  return <MainScrolled.Provider value={scrolled}>{children}</MainScrolled.Provider>;
}

export function useMainScrolled() {
  return useContext(MainScrolled);
}
