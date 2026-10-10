"use client";

import { useRouter } from "next/navigation";
import { Button, ListBox, ListBoxItem, Popover, Select, SelectValue } from "react-aria-components";
import { toast } from "sonner";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/tailgrids/core/tooltip";
import { ChevronDownIcon } from "@/components/ui/icons";
import { m } from "@/i18n";
import { visiblePlatforms, type PlatformDefinition } from "@/platforms/registry";
import { cn } from "@/utils/cn";
import { platformEntry, useActivePlatform } from "./active-platform";
import { startNavigationPending } from "./navigation-pending";
import { useSession } from "./session-provider";

function usePlatforms() {
  const { me } = useSession();
  return visiblePlatforms(me?.platforms as { key: string; order: number }[] | undefined);
}

function useSwitch() {
  const router = useRouter();
  const active = useActivePlatform();
  return (platform: PlatformDefinition) => {
    if (platform.status !== "active") { toast(m.shell.comingSoon(platform.name)); return; }
    const href = platformEntry(platform);
    startNavigationPending(href);
    router.push(href);
    if (platform.key !== active.key) toast.success(m.shell.platformSwitched(platform.name), { duration: 1800 });
  };
}

const SoonBadge = () => <span className="rounded-full bg-background-gray-secondary_alt px-1.5 py-px text-[10px] font-semibold tracking-wide text-text-tertiary uppercase">{m.common.soon}</span>;

/** Desktop: centred segmented pill with one segment per platform. Coming-soon platforms are visible but disabled. */
export function PlatformSwitcher({ className }: { className?: string }) {
  const platforms = usePlatforms();
  const active = useActivePlatform();
  const go = useSwitch();
  return (
    <div role="tablist" aria-label="Platform" className={cn("inline-flex h-10 items-center gap-0.5 rounded-full border border-card-border bg-background-gray-secondary_alt/60 p-1 shadow-xs", className)}>
      {platforms.map((platform) => {
        const selected = platform.key === active.key;
        const soon = platform.status === "coming_soon";
        const segment = (
          <button
            key={platform.key}
            type="button"
            role="tab"
            aria-selected={selected}
            aria-disabled={soon || undefined}
            aria-label={soon ? `${platform.name} (coming soon)` : platform.name}
            onClick={() => go(platform)}
            className={cn(
              "inline-flex h-8 items-center gap-1.5 rounded-full px-3.5 text-sm font-medium whitespace-nowrap transition-all duration-200 focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none [&_svg]:size-4",
              selected ? "bg-card-surface-area text-text-primary shadow-[0_1px_3px_rgba(0,0,0,0.12)] dark:bg-white/10" : soon ? "cursor-not-allowed text-text-tertiary/80" : "text-text-secondary hover:text-text-primary",
            )}
          >
            <span className={selected ? platform.accent : "text-icon-tertiary"}>{platform.icon}</span>
            {platform.name}
            {soon && <SoonBadge />}
          </button>
        );
        if (!soon) return segment;
        return (
          <Tooltip key={platform.key} placement="bottom">
            <TooltipTrigger asChild>{segment}</TooltipTrigger>
            <TooltipContent><p>{platform.name} is coming soon · {platform.description}</p></TooltipContent>
          </Tooltip>
        );
      })}
    </div>
  );
}

/** Mobile: compact dropdown pill. */
export function PlatformSwitcherCompact({ className }: { className?: string }) {
  const platforms = usePlatforms();
  const active = useActivePlatform();
  const go = useSwitch();
  return (
    <Select
      aria-label="Platform"
      selectedKey={active.key}
      disabledKeys={platforms.filter((platform) => platform.status !== "active").map((platform) => platform.key)}
      onSelectionChange={(key) => { const next = platforms.find((platform) => platform.key === key); if (next) go(next); }}
      className={cn("min-w-0", className)}
    >
      <Button className="inline-flex h-9 min-w-0 items-center gap-2 rounded-full border border-card-border bg-card-surface-area/80 pr-2.5 pl-3.5 text-sm font-medium text-text-primary shadow-xs hover:border-primary-500/40 focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none [&_svg]:size-4">
        <span className={active.accent}>{active.icon}</span>
        <SelectValue className="truncate">{() => active.name}</SelectValue>
        <ChevronDownIcon className="text-icon-tertiary" />
      </Button>
      <Popover className="min-w-56 overflow-hidden rounded-xl border border-card-border bg-card-surface-area p-1.5 shadow-lg outline-none entering:animate-pop-in">
        <ListBox className="outline-none">
          {platforms.map((platform) => (
            <ListBoxItem key={platform.key} id={platform.key} textValue={platform.name}
              className="flex cursor-default items-center gap-2.5 rounded-lg px-2.5 py-2.5 text-sm outline-none data-disabled:opacity-60 data-focused:bg-background-gray-secondary_alt data-selected:bg-primary-500/10 [&_svg]:size-4">
              <span className={platform.status === "active" ? platform.accent : "text-icon-tertiary"}>{platform.icon}</span>
              <span className="min-w-0 flex-1"><span className="block font-medium text-text-primary">{platform.name}</span><span className="block truncate text-xs text-text-tertiary">{platform.description}</span></span>
              {platform.status !== "active" && <SoonBadge />}
            </ListBoxItem>
          ))}
        </ListBox>
      </Popover>
    </Select>
  );
}
