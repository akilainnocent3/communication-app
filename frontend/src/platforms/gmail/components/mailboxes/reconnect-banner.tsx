"use client";

import { useState } from "react";
import { WarningIcon } from "@/components/ui/icons";
import { useMailboxSummaries } from "../../api/queries";
import { ConnectLinkDialog } from "./connect-link-dialog";

/** Banner on a mailbox whose Google access was revoked or expired, with a one-click reconnect link. */
export function ReconnectBanner({ mailboxId }: { mailboxId: number }) {
  const box = useMailboxSummaries().find((item) => item.id === mailboxId);
  const [open, setOpen] = useState(false);
  if (!box || (box.status !== "needs_reconnect" && box.status !== "error")) return null;
  const google = box.provider === "gmail_oauth";
  return (
    <div role="alert" className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-warning-500/30 bg-warning-500/10 px-4 py-2.5 text-sm text-text-primary">
      <WarningIcon className="shrink-0 text-warning-500" />
      <span className="min-w-0 flex-1">
        {box.status === "needs_reconnect"
          ? <><b>{box.email}</b> lost its connection. New mail won&apos;t arrive until it is reconnected.</>
          : <><b>{box.email}</b> had a sync problem. Showing the mail synced so far.</>}
      </span>
      {box.permissions.manage && google && (
        <button type="button" onClick={() => setOpen(true)} className="inline-flex h-8 items-center rounded-lg bg-warning-500 px-3 text-xs font-semibold text-black hover:brightness-95">Send reconnect link</button>
      )}
      {box.permissions.manage && !google && <a href={`/gmail/mailboxes/${box.id}`} className="text-xs font-semibold underline">Fix settings</a>}
      {google && <ConnectLinkDialog mailboxId={box.id} email={box.email} isOpen={open} onOpenChange={setOpen} reconnect />}
    </div>
  );
}
