"use client";

import { useState, type ReactNode } from "react";
import { EmptyState } from "@/components/ui/empty-state";
import { InboxIcon } from "@/components/ui/icons";
import { MailboxSummary } from "@/services/api/types";
import { useMailboxScope, useMailboxSummaries } from "../api/queries";
import { MailboxAvatar } from "./mailbox-badges";

/**
 * Per-mailbox tools (labels, filters, signatures, vacation) work on one mailbox. This picks the mailbox selected in the
 * switcher, or the first eligible one when "All mailboxes" is active, and lets the user change it inline.
 */
export function useToolMailbox(eligible: (box: MailboxSummary) => boolean = (box) => box.permissions.manage) {
  const [scope] = useMailboxScope();
  const boxes = useMailboxSummaries().filter((box) => box.status !== "pending" && box.status !== "disabled" && eligible(box));
  const [picked, setPicked] = useState<number | null>(null);
  const id = picked ?? (scope !== "all" && boxes.some((b) => b.id === scope) ? scope : boxes[0]?.id);
  const current = boxes.find((box) => box.id === id);

  const picker: ReactNode = boxes.length > 1 ? (
    <label className="flex min-w-0 items-center gap-2 rounded-lg border border-card-border bg-card-surface-area py-1 pr-2 pl-1.5 text-sm">
      {current && <MailboxAvatar name={current.name} colour={current.colour} size={24} />}
      <span className="sr-only">Mailbox</span>
      <select value={id} onChange={(e) => setPicked(Number(e.target.value))} className="min-w-0 max-w-64 truncate border-0 bg-transparent py-1 pr-7 pl-1 text-sm text-text-primary focus:ring-0">
        {boxes.map((box) => <option key={box.id} value={box.id}>{box.office.name} · {box.email}</option>)}
      </select>
    </label>
  ) : null;

  const empty: ReactNode = (
    <div className="rounded-xl border border-card-border bg-card-surface-area">
      <EmptyState icon={<InboxIcon />} title="No mailbox to manage" body="You need a connected mailbox that you manage to use this tool." />
    </div>
  );

  return { mailbox: current, picker, empty };
}
