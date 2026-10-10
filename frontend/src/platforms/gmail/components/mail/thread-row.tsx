"use client";

import { memo, useRef, useState } from "react";
import { ArchiveIcon, AttachmentIcon, ReadIcon, SnoozeIcon, StarIcon, TrashIcon, UnreadIcon, ImportantIcon, AssignIcon } from "@/components/ui/icons";
import { listTime, fullDate } from "@/lib/format";
import type { SwipeAction, ThreadSummary } from "@/services/api/types";
import { cn } from "@/utils/cn";
import { senderLine } from "./participants";

export type RowAction = "archive" | "trash" | "read" | "unread" | "star" | "unstar" | "snooze";

type Props = {
  thread: ThreadSummary;
  selected: boolean;
  focused: boolean;
  active: boolean;
  showMailbox: boolean;
  compact: boolean;
  canOrganise: boolean;
  canDelete: boolean;
  swipeLeft: SwipeAction;
  swipeRight: SwipeAction;
  onOpen: (thread: ThreadSummary) => void;
  onToggleSelect: (thread: ThreadSummary, range: boolean) => void;
  onAction: (thread: ThreadSummary, action: RowAction) => void;
  onSnooze: (thread: ThreadSummary, anchor: HTMLElement) => void;
  onHover: (thread: ThreadSummary) => void;
};

const SWIPE_META: Record<Exclude<SwipeAction, "none">, { label: string; icon: React.ReactNode; tone: string }> = {
  archive: { label: "Archive", icon: <ArchiveIcon />, tone: "bg-success-500" },
  trash: { label: "Delete", icon: <TrashIcon />, tone: "bg-error-500" },
  read: { label: "Read", icon: <ReadIcon />, tone: "bg-primary-500" },
};

function QuickButton({ label, onClick, children }: { label: string; onClick: (event: React.MouseEvent<HTMLButtonElement>) => void; children: React.ReactNode }) {
  return (
    <button type="button" aria-label={label} title={label} onClick={(event) => { event.stopPropagation(); onClick(event); }}
      className="flex size-8 items-center justify-center rounded-full text-icon-secondary transition-colors hover:bg-background-gray-secondary hover:text-text-primary focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none [&_svg]:size-[18px]">
      {children}
    </button>
  );
}

/** One conversation in the list. Desktop: hover quick actions. Touch: swipe left/right for the configured actions. */
function ThreadRowBase({ thread, selected, focused, active, showMailbox, compact, canOrganise, canDelete, swipeLeft, swipeRight, onOpen, onToggleSelect, onAction, onSnooze, onHover }: Props) {
  const unread = !!thread.is_unread;
  const sender = senderLine(thread.participants, thread.message_count);
  const [dx, setDx] = useState(0);
  const start = useRef<{ x: number; y: number; locked?: "x" | "y" } | null>(null);
  const swipeFor = (direction: "left" | "right") => {
    const action = direction === "right" ? swipeRight : swipeLeft;
    if (action === "none") return null;
    if (action === "trash" && !canDelete) return null;
    if (action === "archive" && !canOrganise) return null;
    return action;
  };
  const pending = dx > 0 ? swipeFor("right") : dx < 0 ? swipeFor("left") : null;
  const threshold = 96;

  const onTouchStart = (event: React.TouchEvent) => { start.current = { x: event.touches[0].clientX, y: event.touches[0].clientY }; };
  const onTouchMove = (event: React.TouchEvent) => {
    const origin = start.current;
    if (!origin) return;
    const deltaX = event.touches[0].clientX - origin.x;
    const deltaY = event.touches[0].clientY - origin.y;
    if (!origin.locked && (Math.abs(deltaX) > 8 || Math.abs(deltaY) > 8)) origin.locked = Math.abs(deltaX) > Math.abs(deltaY) ? "x" : "y";
    if (origin.locked === "x" && swipeFor(deltaX > 0 ? "right" : "left")) setDx(Math.max(-160, Math.min(160, deltaX)));
  };
  const onTouchEnd = () => {
    if (pending && Math.abs(dx) > threshold) onAction(thread, pending === "read" ? (unread ? "read" : "unread") : pending);
    start.current = null;
    setDx(0);
  };
  const meta = pending ? SWIPE_META[pending] : null;
  const userLabels = thread.labels ?? [];
  const assigned = thread.assignment as { assignee?: { display_name?: string } } | null;

  return (
    <div className="@container relative overflow-hidden" data-thread-row={thread.id}>
      {meta && (
        <div aria-hidden="true" className={cn("absolute inset-0 flex items-center px-6 text-white", meta.tone, dx > 0 ? "justify-start" : "justify-end")}>
          <span className={cn("flex items-center gap-2 text-sm font-medium transition-transform", Math.abs(dx) > threshold && "scale-110")}>{meta.icon}{meta.label}</span>
        </div>
      )}
      <div
        role="row"
        aria-selected={selected}
        aria-current={active ? "true" : undefined}
        tabIndex={focused ? 0 : -1}
        onClick={(event) => (event.shiftKey || event.metaKey || event.ctrlKey ? onToggleSelect(thread, event.shiftKey) : onOpen(thread))}
        onKeyDown={(event) => { if (event.key === "Enter" && event.target === event.currentTarget) onOpen(thread); }}
        onMouseEnter={() => onHover(thread)}
        onTouchStart={onTouchStart}
        onTouchMove={onTouchMove}
        onTouchEnd={onTouchEnd}
        style={dx ? { transform: `translateX(${dx}px)` } : undefined}
        className={cn(
          "group/row relative flex cursor-pointer items-center gap-1 border-b border-card-border/70 bg-card-surface-area pr-3 pl-1.5 transition-[background-color,transform] duration-150 outline-none select-none sm:pl-2",
          compact ? "min-h-10 py-1" : "min-h-[72px] py-2 sm:min-h-14 sm:py-1.5",
          !unread && "bg-background-gray-secondary_alt/35 dark:bg-white/[0.015]",
          selected && "bg-primary-500/8! dark:bg-primary-500/12!",
          active && "bg-primary-500/10! before:absolute before:inset-y-0 before:left-0 before:w-[3px] before:bg-primary-500",
          focused && "ring-2 ring-primary-500/60 ring-inset",
          "hover:z-10 hover:shadow-[inset_1px_0_0_var(--color-card-border),inset_-1px_0_0_var(--color-card-border),0_1px_2px_0_rgba(60,64,67,0.2),0_1px_3px_1px_rgba(60,64,67,0.1)]",
        )}
      >
        <label className="flex size-10 shrink-0 items-center justify-center rounded-full hover:bg-background-gray-secondary_alt" onClick={(event) => event.stopPropagation()}>
          <input type="checkbox" checked={selected} onChange={(event) => onToggleSelect(thread, (event.nativeEvent as MouseEvent).shiftKey)} aria-label={`Select conversation: ${thread.subject || "(no subject)"}`}
            className="size-4 rounded border-border-primary text-primary-500 focus:ring-primary-500" />
        </label>
        <button type="button" onClick={(event) => { event.stopPropagation(); onAction(thread, thread.is_starred ? "unstar" : "star"); }}
          aria-label={thread.is_starred ? "Unstar" : "Star"} aria-pressed={!!thread.is_starred}
          className={cn("hidden size-8 shrink-0 items-center justify-center rounded-full hover:bg-background-gray-secondary_alt focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none sm:flex", thread.is_starred ? "text-warning-500" : "text-icon-tertiary")}>
          <StarIcon size={18} fill={thread.is_starred ? "currentColor" : "none"} />
        </button>
        {thread.is_important && <span className="hidden text-warning-500 sm:inline" title="Important"><ImportantIcon size={14} fill="currentColor" /><span className="sr-only">Important</span></span>}

        <div className={cn("flex min-w-0 flex-1 gap-x-3", compact ? "items-center" : "flex-col @2xl:flex-row @2xl:items-center")}>
          <div className={cn("flex min-w-0 shrink-0 items-center gap-2", compact ? "w-36 @3xl:w-52" : "@2xl:w-40 @3xl:w-52")}>
            {showMailbox && <span aria-hidden="true" className="size-2 shrink-0 rounded-full" style={{ background: thread.mailbox.colour }} title={thread.mailbox.name} />}
            <span className={cn("truncate text-sm", unread ? "font-semibold text-text-primary" : "text-text-secondary")}>
              {sender.text}
            </span>
            {sender.count && <span className="shrink-0 text-xs text-text-tertiary">{sender.count}</span>}
            {!compact && <span className={cn("ml-auto shrink-0 text-xs @2xl:hidden", unread ? "font-semibold text-text-primary" : "text-text-tertiary")}>{listTime(thread.last_message_at)}</span>}
          </div>
          <div className="flex min-w-0 flex-1 items-center gap-2">
            {showMailbox && <span className="hidden shrink-0 rounded-md px-1.5 text-[11px] font-medium @4xl:inline" style={{ background: `${thread.mailbox.colour}1f`, color: thread.mailbox.colour }}>{thread.mailbox.office || thread.mailbox.name}</span>}
            {userLabels.slice(0, 3).map((label, index) => (
              <span key={label.id} className={cn("hidden shrink-0 rounded px-1.5 text-[11px] leading-[18px] font-medium", index === 0 ? "@3xl:inline" : "@5xl:inline")} style={{ background: label.colour || "#e5e7eb", color: label.text_colour || "#111827" }}>{label.name}</span>
            ))}
            <p className="min-w-0 truncate text-sm">
              <span className={unread ? "font-semibold text-text-primary" : "text-text-primary"}>{thread.subject || "(no subject)"}</span>
              {thread.snippet && <span className="text-text-tertiary"> – {thread.snippet}</span>}
            </p>
          </div>
        </div>

        <div className="ml-2 flex shrink-0 items-center gap-2">
          {assigned?.assignee?.display_name && <span className="hidden text-icon-tertiary xl:inline" title={`Assigned to ${assigned.assignee.display_name}`}><AssignIcon size={16} /></span>}
          {thread.snoozed_until && <span className="hidden text-warning-500 sm:inline" title={`Snoozed until ${fullDate(thread.snoozed_until)}`}><SnoozeIcon size={16} /></span>}
          {thread.has_attachments && <span className="text-icon-tertiary" title="Has attachments"><AttachmentIcon size={16} /><span className="sr-only">Has attachments</span></span>}
          <time dateTime={thread.last_message_at} title={fullDate(thread.last_message_at)}
            className={cn("w-14 text-right text-xs tabular-nums group-hover/row:invisible max-sm:group-hover/row:visible", !compact && "@max-2xl:hidden", unread ? "font-semibold text-text-primary" : "text-text-tertiary")}>
            {listTime(thread.last_message_at)}
          </time>
        </div>

        <div className="absolute inset-y-0 right-0 hidden items-center gap-0.5 bg-card-surface-area pr-2 pl-1 shadow-[-16px_0_12px_-4px_var(--color-card-surface-area)] sm:group-hover/row:flex sm:group-focus-within/row:flex">
          {canOrganise && <QuickButton label="Archive (e)" onClick={() => onAction(thread, "archive")}><ArchiveIcon /></QuickButton>}
          {canDelete && <QuickButton label="Delete (#)" onClick={() => onAction(thread, "trash")}><TrashIcon /></QuickButton>}
          <QuickButton label={unread ? "Mark as read" : "Mark as unread"} onClick={() => onAction(thread, unread ? "read" : "unread")}>{unread ? <ReadIcon /> : <UnreadIcon />}</QuickButton>
          {canOrganise && <QuickButton label="Snooze (b)" onClick={(event) => onSnooze(thread, event.currentTarget)}><SnoozeIcon /></QuickButton>}
        </div>
      </div>
    </div>
  );
}

export const ThreadRow = memo(ThreadRowBase);
