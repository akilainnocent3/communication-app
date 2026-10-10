"use client";

import { useVirtualizer } from "@tanstack/react-virtual";
import { useEffect, useRef } from "react";
import { Skeleton } from "@/components/tailgrids/core/skeleton";
import { ActivityIndicator } from "@/components/ui/activity-indicator";
import type { SwipeAction, ThreadSummary } from "@/services/api/types";
import { cn } from "@/utils/cn";
import { ThreadRow, type RowAction } from "./thread-row";

export function ListSkeleton({ rows = 12, compact }: { rows?: number; compact?: boolean }) {
  return (
    <div role="status" aria-label="Loading conversations">
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className={cn("flex items-center gap-3 border-b border-card-border/70 px-4", compact ? "h-10" : "h-[72px] sm:h-14")}>
          <Skeleton className="size-4 rounded" />
          <Skeleton className="hidden size-4 rounded sm:block" />
          <div className="flex min-w-0 flex-1 flex-col gap-2 sm:flex-row sm:items-center sm:gap-4">
            <Skeleton className="h-3.5 w-32 shrink-0 sm:w-44" />
            <Skeleton className="h-3.5" style={{ width: `${45 + ((index * 17) % 40)}%` }} />
          </div>
          <Skeleton className="h-3 w-10 shrink-0" />
        </div>
      ))}
    </div>
  );
}

type Props = {
  threads: ThreadSummary[];
  hasMore: boolean;
  loadingMore: boolean;
  onLoadMore: () => void;
  selected: Set<number>;
  focusedId: number | null;
  activeId: number | null;
  showMailbox: boolean;
  compact: boolean;
  swipeLeft: SwipeAction;
  swipeRight: SwipeAction;
  permissionsFor: (thread: ThreadSummary) => { send: boolean; delete: boolean };
  onOpen: (thread: ThreadSummary) => void;
  onToggleSelect: (thread: ThreadSummary, range: boolean) => void;
  onAction: (thread: ThreadSummary, action: RowAction) => void;
  onSnooze: (thread: ThreadSummary, anchor: HTMLElement) => void;
  onHover: (thread: ThreadSummary) => void;
  footer?: React.ReactNode;
};

/** Virtualised conversation list with infinite scroll; keeps the focused row in view for j/k. */
export function ThreadList(props: Props) {
  const { threads, hasMore, loadingMore, onLoadMore, focusedId, compact, footer } = props;
  const parent = useRef<HTMLDivElement>(null);
  // TanStack Virtual returns fresh functions each render; the React Compiler skips this component, which is fine.
  // eslint-disable-next-line react-hooks/incompatible-library
  const virtualizer = useVirtualizer({
    count: threads.length + (hasMore ? 1 : 0),
    getScrollElement: () => parent.current,
    estimateSize: () => (compact ? 41 : 73),
    overscan: 10,
    getItemKey: (index) => threads[index]?.id ?? "more",
  });
  const items = virtualizer.getVirtualItems();
  const lastIndex = items[items.length - 1]?.index ?? 0;

  useEffect(() => {
    if (hasMore && !loadingMore && lastIndex >= threads.length - 8) onLoadMore();
  }, [hasMore, loadingMore, lastIndex, threads.length, onLoadMore]);

  const focusedIndex = focusedId === null ? -1 : threads.findIndex((thread) => thread.id === focusedId);
  useEffect(() => {
    if (focusedIndex >= 0) virtualizer.scrollToIndex(focusedIndex, { align: "auto" });
  }, [focusedIndex, virtualizer]);

  return (
    <div ref={parent} role="grid" aria-label="Conversations" aria-rowcount={threads.length} className="scrollbar-thin min-h-0 flex-1 overflow-y-auto overscroll-contain">
      <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
        {items.map((item) => {
          const thread = threads[item.index];
          return (
            <div key={item.key} data-index={item.index} ref={virtualizer.measureElement} style={{ position: "absolute", top: 0, left: 0, right: 0, transform: `translateY(${item.start}px)` }}>
              {thread ? (
                <ThreadRow
                  thread={thread}
                  selected={props.selected.has(thread.id)}
                  focused={thread.id === focusedId}
                  active={thread.id === props.activeId}
                  showMailbox={props.showMailbox}
                  compact={compact}
                  canOrganise={props.permissionsFor(thread).send}
                  canDelete={props.permissionsFor(thread).delete}
                  swipeLeft={props.swipeLeft}
                  swipeRight={props.swipeRight}
                  onOpen={props.onOpen}
                  onToggleSelect={props.onToggleSelect}
                  onAction={props.onAction}
                  onSnooze={props.onSnooze}
                  onHover={props.onHover}
                />
              ) : (
                <div className="flex h-14 items-center justify-center"><ActivityIndicator size="sm" label="Loading more conversations" /></div>
              )}
            </div>
          );
        })}
      </div>
      {!hasMore && footer}
    </div>
  );
}
