"use client";

import { useVirtualizer } from "@tanstack/react-virtual";
import { useEffect, useRef } from "react";
import { Skeleton } from "@/components/tailgrids/core/skeleton";
import { ActivityIndicator } from "@/components/ui/activity-indicator";
import { Chip } from "@/components/ui/status-pill";
import { useHeldOrder } from "@/hooks/use-held-order";
import { m } from "@/i18n";
import { listTime } from "@/lib/format";
import type { CallSummary } from "@/services/api/types";
import { cn } from "@/utils/cn";
import { DirectionIcon, callTitle, duration, isMissed, resultLabel } from "../lib/labels";

export function CallListSkeleton({ rows = 10 }: { rows?: number }) {
  return (
    <div role="status" aria-label="Loading calls">
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="flex h-16 items-center gap-3 border-b border-card-border/70 px-4">
          <Skeleton className="size-5 rounded-full" />
          <div className="flex-1 space-y-2"><Skeleton className="h-3.5 w-40" /><Skeleton className="h-3" style={{ width: `${35 + ((index * 13) % 40)}%` }} /></div>
          <Skeleton className="h-3 w-12" />
        </div>
      ))}
    </div>
  );
}

function CallRow({ call, active, showDevice, onOpen }: { call: CallSummary; active: boolean; showDevice: boolean; onOpen: (call: CallSummary) => void }) {
  const missed = isMissed(call);
  return (
    <button type="button" data-call-row={call.id} data-result={call.result} onClick={() => onOpen(call)} aria-current={active || undefined}
      className={cn("@container flex w-full items-center gap-3 border-b border-card-border/70 px-4 py-2.5 text-left transition-colors hover:bg-background-gray-secondary_alt focus-visible:bg-background-gray-secondary_alt focus-visible:outline-none",
        active && "bg-primary-500/8")}>
      <DirectionIcon call={call} size={18} />
      <span className="min-w-0 flex-1">
        <span className={cn("flex items-center gap-1.5 truncate text-sm font-medium", missed ? "text-error-600 dark:text-error-400" : "text-text-primary")}>
          <span className="truncate">{callTitle(call)}</span>
          {call.name && call.display_number && <span className="hidden truncate font-normal text-text-tertiary @md:inline">{call.display_number}</span>}
          {call.name_source === "directory" && <Chip className="hidden @lg:inline-flex" title={m.calls.nameFromDirectory}>Directory</Chip>}
        </span>
        <span className="flex flex-wrap items-center gap-x-2 truncate text-xs text-text-tertiary">
          <span>{call.is_final ? resultLabel(call.result) : m.calls.ringing}</span>
          {call.talk_seconds > 0 && <span className="tabular-nums">{duration(call.talk_seconds)}</span>}
          {call.direction === "in" && call.result === "answered" && <span className="hidden tabular-nums @md:inline">rang {duration(call.ring_seconds)}</span>}
          {call.sim && <span className="inline-flex items-center gap-1"><span aria-hidden="true" className="size-1.5 rounded-full" style={{ background: call.sim.colour }} />{call.sim.label}</span>}
          {showDevice && <span className="truncate">{call.device.name}</span>}
          {call.is_after_hours && <span>After hours</span>}
          {missed && call.returned_at && <span className="text-success-600 dark:text-success-400">Returned</span>}
          {call.deleted_on_device && <span>{m.calls.deletedOnPhone}</span>}
        </span>
      </span>
      {call.outcome && <Chip className="hidden shrink-0 @sm:inline-flex" style={{ borderColor: call.outcome.colour, color: call.outcome.colour }}>{call.outcome.name}</Chip>}
      <time dateTime={call.started_at} className="shrink-0 text-xs tabular-nums text-text-tertiary">{listTime(call.started_at)}</time>
    </button>
  );
}

/** Virtualised call log with infinite scroll. Rows hold their order under the pointer (useHeldOrder, decision 61). */
export function CallList({ rows: latest, hasMore, loadingMore, onLoadMore, activeId, showDevice, onOpen }: {
  rows: CallSummary[]; hasMore: boolean; loadingMore: boolean; onLoadMore: () => void; activeId: number | null; showDevice: boolean; onOpen: (call: CallSummary) => void;
}) {
  const parent = useRef<HTMLDivElement>(null);
  const { rows, handlers } = useHeldOrder(latest);
  // eslint-disable-next-line react-hooks/incompatible-library -- TanStack Virtual returns fresh functions each render
  const virtualizer = useVirtualizer({
    count: rows.length + (hasMore ? 1 : 0),
    getScrollElement: () => parent.current,
    estimateSize: () => 61,
    overscan: 12,
    getItemKey: (index) => rows[index]?.id ?? "more",
  });
  const items = virtualizer.getVirtualItems();
  const lastIndex = items[items.length - 1]?.index ?? 0;
  useEffect(() => {
    if (hasMore && !loadingMore && lastIndex >= rows.length - 8) onLoadMore();
  }, [hasMore, loadingMore, lastIndex, rows.length, onLoadMore]);
  return (
    <div ref={parent} {...handlers} role="list" aria-label="Calls" className="scrollbar-thin min-h-0 flex-1 overflow-y-auto overscroll-contain">
      <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
        {items.map((item) => {
          const row = rows[item.index];
          return (
            <div key={item.key} role="listitem" data-index={item.index} ref={virtualizer.measureElement} style={{ position: "absolute", top: 0, left: 0, right: 0, transform: `translateY(${item.start}px)` }}>
              {row ? <CallRow call={row} active={row.id === activeId} showDevice={showDevice} onOpen={onOpen} />
                : <div className="flex h-14 items-center justify-center"><ActivityIndicator size="sm" label="Loading more calls" /></div>}
            </div>
          );
        })}
      </div>
    </div>
  );
}
