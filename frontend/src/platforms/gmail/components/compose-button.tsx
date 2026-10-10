"use client";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/tailgrids/core/tooltip";
import { PencilIcon } from "@/components/ui/icons";
import { cn } from "@/utils/cn";
import { useCurrentMailbox, useMailboxSummaries } from "../api/queries";
import { openCompose } from "../compose/store";

/** Sidebar's prominent Compose button (and the mobile FAB uses `openCompose` directly). */
export function ComposeButton({ collapsed, onAction }: { collapsed: boolean; onAction?: () => void }) {
  const current = useCurrentMailbox();
  const mailboxes = useMailboxSummaries();
  const canSend = current ? current.permissions.send : mailboxes.some((box) => box.permissions.send);
  if (!canSend) return null;
  const open = () => { openCompose({ mailbox: current?.id }); onAction?.(); };
  const className = "flex items-center justify-center gap-2 rounded-xl bg-primary-500 font-medium text-white shadow-[0_6px_16px_-6px_rgba(55,88,249,0.55)] transition hover:bg-primary-600 focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2 focus-visible:ring-offset-card-surface-area focus-visible:outline-none active:scale-[0.98]";
  if (collapsed)
    return (
      <Tooltip placement="right">
        <TooltipTrigger asChild>
          <button type="button" onClick={open} aria-label="Compose (c)" className={cn(className, "size-11")}><PencilIcon /></button>
        </TooltipTrigger>
        <TooltipContent><p>Compose</p></TooltipContent>
      </Tooltip>
    );
  return (
    <button type="button" onClick={open} className={cn(className, "h-11 w-full text-sm")}>
      <PencilIcon /> Compose
      <kbd className="ml-1 rounded border border-white/30 px-1.5 text-[11px] leading-4 font-normal text-white/80">c</kbd>
    </button>
  );
}
