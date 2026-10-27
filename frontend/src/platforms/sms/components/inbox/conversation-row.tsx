"use client";

import { memo } from "react";
import { ArchiveIcon, AssignIcon, AttachmentIcon, LockIcon, MuteIcon, PinIcon, ReadIcon, UnreadIcon } from "@/components/ui/icons";
import { avatarHue, fullDate, initials, listTime } from "@/lib/format";
import type { ConversationSummary } from "@/services/api/types";
import { cn } from "@/utils/cn";
import { StatusIcon } from "../chat/message-bubble";

export type RowAction = "archive" | "unarchive" | "read" | "unread" | "pin" | "unpin";

type Props = {
  row: ConversationSummary;
  selected: boolean;
  focused: boolean;
  active: boolean;
  showDevice: boolean;
  showSim: boolean;
  canOrganise: boolean;
  onOpen: (row: ConversationSummary) => void;
  onToggleSelect: (row: ConversationSummary, range: boolean) => void;
  onAction: (row: ConversationSummary, action: RowAction) => void;
};

function Avatar({ row }: { row: ConversationSummary }) {
  const first = row.participants[0];
  const name = first?.name || "";
  const hue = avatarHue(first?.address ?? row.title);
  const label = row.is_group ? `${row.participants.length}` : name ? initials(name) : first?.kind === "alphanumeric" ? initials(first.display) : "#";
  return (
    <span aria-hidden="true" className="flex size-10 shrink-0 items-center justify-center rounded-full text-sm font-semibold text-white" style={{ background: `hsl(${hue} 55% 45%)` }}>
      {label}
    </span>
  );
}

function QuickButton({ label, onClick, children }: { label: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" aria-label={label} title={label} onClick={(event) => { event.stopPropagation(); onClick(); }}
      className="flex size-8 items-center justify-center rounded-full text-icon-secondary transition-colors hover:bg-background-gray-secondary hover:text-text-primary focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none [&_svg]:size-[18px]">
      {children}
    </button>
  );
}

/** One conversation: contact name (or formatted number), snippet, time, unread count, SIM, assignment and last status. */
function ConversationRowBase({ row, selected, focused, active, showDevice, showSim, canOrganise, onOpen, onToggleSelect, onAction }: Props) {
  const unread = row.unread_count > 0;
  const savedName = row.participants.length === 1 && row.participants[0].name;
  return (
    <div
      role="row" aria-selected={selected} aria-current={active ? "true" : undefined} tabIndex={focused ? 0 : -1} data-conversation-row={row.id}
      onClick={(event) => (event.shiftKey || event.metaKey || event.ctrlKey ? onToggleSelect(row, event.shiftKey) : onOpen(row))}
      onKeyDown={(event) => { if (event.key === "Enter" && event.target === event.currentTarget) onOpen(row); }}
      className={cn(
        "group/row relative flex min-h-[72px] cursor-pointer items-center gap-3 border-b border-card-border/70 bg-card-surface-area py-2 pr-3 pl-2 outline-none select-none",
        !unread && "bg-background-gray-secondary_alt/35 dark:bg-white/[0.015]",
        selected && "bg-primary-500/8! dark:bg-primary-500/12!",
        active && "bg-primary-500/10! before:absolute before:inset-y-0 before:left-0 before:w-[3px] before:bg-primary-500",
        focused && "ring-2 ring-primary-500/60 ring-inset",
        "hover:bg-background-gray-secondary_alt/60",
      )}
    >
      <label className="flex size-8 shrink-0 items-center justify-center rounded-full hover:bg-background-gray-secondary_alt" onClick={(event) => event.stopPropagation()}>
        <input type="checkbox" checked={selected} onChange={(event) => onToggleSelect(row, (event.nativeEvent as MouseEvent).shiftKey)} aria-label={`Select conversation: ${row.title}`}
          className="size-4 rounded border-border-primary text-primary-500 focus:ring-primary-500" />
      </label>
      <Avatar row={row} />
      <div className="min-w-0 flex-1">
        <div className="flex min-w-0 items-center gap-1.5">
          {showDevice && <span aria-hidden="true" className="size-2 shrink-0 rounded-full" style={{ background: row.device.colour }} title={row.device.name} />}
          <span className={cn("truncate text-sm", unread ? "font-semibold text-text-primary" : "text-text-primary")}>{row.title}</span>
          {savedName && <span className="hidden shrink-0 truncate text-xs text-text-tertiary @md:inline">{row.participants[0].display}</span>}
          {row.is_pinned && <PinIcon size={13} className="shrink-0 text-icon-tertiary" aria-label="Pinned" />}
          {row.is_muted && <MuteIcon size={13} className="shrink-0 text-icon-tertiary" aria-label="Muted" />}
          <time dateTime={row.last_message_at} title={fullDate(row.last_message_at)} className={cn("ml-auto shrink-0 pl-2 text-xs tabular-nums", unread ? "font-semibold text-text-primary" : "text-text-tertiary")}>
            {listTime(row.last_message_at)}
          </time>
        </div>
        <div className="mt-0.5 flex min-w-0 items-center gap-1.5">
          {row.last_direction === "out" && <StatusIcon status={row.last_status} className={row.last_status === "failed" ? "text-error-500" : "text-icon-tertiary"} />}
          {row.snippet_sensitive && <LockIcon size={12} className="shrink-0 text-icon-tertiary" aria-label="Sensitive" />}
          {row.has_mms && <AttachmentIcon size={13} className="shrink-0 text-icon-tertiary" aria-label="Has MMS" />}
          <p className={cn("min-w-0 flex-1 truncate text-sm", unread ? "text-text-primary" : "text-text-tertiary")}>{row.snippet}</p>
          {showSim && row.sim && <span className="shrink-0 rounded px-1 text-[10px] font-semibold" style={{ background: `${row.sim.colour}22`, color: row.sim.colour }}>{row.sim.label}</span>}
          {row.assigned_to && <span className="shrink-0 text-icon-tertiary" title={`Assigned to ${row.assigned_to.display_name}`}><AssignIcon size={14} /></span>}
          {unread && <span className="flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full bg-primary-500 px-1.5 text-[11px] font-semibold text-white tabular-nums" aria-label={`${row.unread_count} unread`}>{row.unread_count}</span>}
        </div>
      </div>
      <div className="absolute inset-y-0 right-0 hidden items-center gap-0.5 bg-card-surface-area pr-2 pl-1 shadow-[-16px_0_12px_-4px_var(--color-card-surface-area)] sm:group-hover/row:flex sm:group-focus-within/row:flex">
        {canOrganise && <QuickButton label={row.is_archived ? "Move to inbox" : "Archive (e)"} onClick={() => onAction(row, row.is_archived ? "unarchive" : "archive")}><ArchiveIcon /></QuickButton>}
        <QuickButton label={unread ? "Mark as read" : "Mark as unread"} onClick={() => onAction(row, unread ? "read" : "unread")}>{unread ? <ReadIcon /> : <UnreadIcon />}</QuickButton>
        {canOrganise && <QuickButton label={row.is_pinned ? "Unpin" : "Pin"} onClick={() => onAction(row, row.is_pinned ? "unpin" : "pin")}><PinIcon /></QuickButton>}
      </div>
    </div>
  );
}

export const ConversationRow = memo(ConversationRowBase);
