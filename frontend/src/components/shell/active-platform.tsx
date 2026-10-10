"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { readStored, writeStored } from "@/lib/storage";
import { PLATFORMS, platformForPath, type PlatformDefinition } from "@/platforms/registry";

const LAST_PLATFORM = "cm:last-platform";
const lastRouteKey = (key: string) => `cm:last-route:${key}`;

/**
 * The active platform comes from the first URL segment. Shared pages (/settings) keep the platform the user came
 * from, so its sidebar stays in place.
 */
export function useActivePlatform(): PlatformDefinition {
  const pathname = usePathname();
  const fromPath = platformForPath(pathname);
  const fallback = PLATFORMS.find((platform) => platform.key === readStored(LAST_PLATFORM, "gmail") && platform.status === "active") ?? PLATFORMS[0];
  const active = fromPath && fromPath.status === "active" ? fromPath : fallback;
  useEffect(() => {
    if (!fromPath || fromPath.status !== "active" || !pathname) return;
    writeStored(LAST_PLATFORM, fromPath.key);
    writeStored(lastRouteKey(fromPath.key), pathname + window.location.search);
  }, [fromPath, pathname]);
  return active;
}

/** Where switching to a platform goes: its last visited route, or its home. */
export function platformEntry(platform: PlatformDefinition): string {
  const last = readStored<string | null>(lastRouteKey(platform.key), null);
  return last && last.startsWith(platform.basePath) ? last : platform.homePath;
}
