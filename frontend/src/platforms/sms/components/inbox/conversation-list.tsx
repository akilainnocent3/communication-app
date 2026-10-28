"use client";

import { useVirtualizer } from "@tanstack/react-virtual";
import { useEffect, useRef } from "react";
import { Skeleton } from "@/components/tailgrids/core/skeleton";
import { ActivityIndicator } from "@/components/ui/activity-indicator";
import { useHeldOrder } from "@/hooks/use-held-order";
import type { ConversationSummary } from "@/services/api/types";
import { ConversationRow, type RowAction } from "./conversation-row";

export function ConversationListSkeleton({ rows = 10 }: { rows?: number }) {
  return (
    <div role="status" aria-label="Loading conversations">
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="flex h-[72px] items-center gap-3 border-b border-card-border/70 px-4">
          <Skeleton className="size-10 rounded-full" />
          <div className="flex-1 space-y-2"><Skeleton className="h-3.5 w-40" /><Skeleton className="h-3" style={{ width: `${45 + ((index * 17) % 40)}%` }} /></div>
          <Skeleton className="h-3 w-10" />
        </div>
      ))}
    </div>
  );
}

type Props = {
  rows: ConversationSummary[];
  hasMore: boolean;
  loadingMore: boolean;
  onLoadMore: () => void;
  selected: Set<number>;
  focusedId: number | null;
  activeId: number | null;
  showDevice: boolean;
  showSim: boolean;
  canOrganise: (row: ConversationSummary) => boolean;
  onOpen: (row: ConversationSummary) => void;
  onToggleSelect: (row: ConversationSummary, range: boolean) => void;
  onAction: (row: ConversationSummary, action: RowAction) => void;
};

/**
 * Virtualised conversation list with infinite scroll; keeps the focused row in view for j/k. Rows keep their positions
 * while the pointer is on them (useHeldOrder), so a poll that re-sorts the list can never move a row mid-tap.
 */
export function ConversationList(props: Props) {
  const { hasMore, loadingMore, onLoadMore, focusedId } = props;
  const { rows, handlers } = useHeldOrder(props.rows);
  const parent = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line react-hooks/incompatible-library -- TanStack Virtual returns fresh functions each render
  const virtualizer = useVirtualizer({
    count: rows.length + (hasMore ? 1 : 0),
    getScrollElement: () => parent.current,
    estimateSize: () => 73,
    overscan: 10,
    getItemKey: (index) => rows[index]?.id ?? "more",
  });
  const items = virtualizer.getVirtualItems();
  const lastIndex = items[items.length - 1]?.index ?? 0;
  useEffect(() => {
    if (hasMore && !loadingMore && lastIndex >= rows.length - 8) onLoadMore();
  }, [hasMore, loadingMore, lastIndex, rows.length, onLoadMore]);
  const focusedIndex = focusedId === null ? -1 : rows.findIndex((row) => row.id === focusedId);
  useEffect(() => {
    if (focusedIndex >= 0) virtualizer.scrollToIndex(focusedIndex, { align: "auto" });
  }, [focusedIndex, virtualizer]);

  return (
    <div ref={parent} {...handlers} role="grid" aria-label="Conversations" aria-rowcount={rows.length} className="@container scrollbar-thin min-h-0 flex-1 overflow-y-auto overscroll-contain">
      <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
        {items.map((item) => {
          const row = rows[item.index];
          return (
            <div key={item.key} data-index={item.index} ref={virtualizer.measureElement} style={{ position: "absolute", top: 0, left: 0, right: 0, transform: `translateY(${item.start}px)` }}>
              {row ? (
                <ConversationRow row={row} selected={props.selected.has(row.id)} focused={row.id === focusedId} active={row.id === props.activeId} showDevice={props.showDevice}
                  showSim={props.showSim} canOrganise={props.canOrganise(row)} onOpen={props.onOpen} onToggleSelect={props.onToggleSelect} onAction={props.onAction} />
              ) : (
                <div className="flex h-14 items-center justify-center"><ActivityIndicator size="sm" label="Loading more conversations" /></div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
