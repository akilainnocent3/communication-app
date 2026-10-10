/**
 * Platform registry. Each communication channel is one `PlatformDefinition`; the shell (sidebar, switcher,
 * ⌘K palette, context bar) reads only from here. See docs/adding-a-platform.md.
 */
import { gmail } from "./gmail/definition";
import { callsComingSoon, mediaComingSoon, smsComingSoon } from "./coming-soon";
import type { PlatformDefinition } from "./types";

export type { PlatformDefinition, PlatformNavItem, PlatformNavChild, PlatformNavSection, CommandDef } from "./types";

export const PLATFORMS: PlatformDefinition[] = [gmail, smsComingSoon, callsComingSoon, mediaComingSoon];

/** The platform owning a pathname (first URL segment), if any. */
export function platformForPath(pathname: string | null): PlatformDefinition | undefined {
  const segment = `/${(pathname ?? "").split("/")[1] ?? ""}`;
  return PLATFORMS.find((platform) => platform.basePath === segment);
}

/**
 * Platforms the user sees in the switcher: the code registry ∩ GET /platforms/ (enabled + permitted), in the
 * server's order. Coming-soon entries are always listed (disabled) so staff know what is planned.
 */
export function visiblePlatforms(server: { key: string; order: number }[] | undefined): PlatformDefinition[] {
  const order = new Map((server ?? []).map((item) => [item.key, item.order]));
  const active = PLATFORMS.filter((platform) => platform.status === "active" && order.has(platform.key))
    .sort((a, b) => (order.get(a.key) ?? 0) - (order.get(b.key) ?? 0));
  return [...active, ...PLATFORMS.filter((platform) => platform.status === "coming_soon")];
}
