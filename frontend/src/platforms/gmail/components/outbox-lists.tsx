"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/tailgrids/core/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ClockIcon, DraftIcon, TrashIcon } from "@/components/ui/icons";
import { Page, PageHeader } from "@/components/ui/page";
import { RequestState, TableSkeleton } from "@/components/ui/request-state";
import { StatusPill } from "@/components/ui/status-pill";
import { dateTime, listTime } from "@/lib/format";
import { errorMessage, mutate } from "@/services/api/client";
import type { Address } from "@/services/api/types";
import { mailKeys } from "../api/keys";
import { useDrafts, useMailboxScope, useMailboxSummaries, useScheduled } from "../api/queries";
import { openCompose } from "../compose/store";
import { cancelSend } from "../compose/send-toast";
import { cn } from "@/utils/cn";

const recipients = (to: Address[]) => to.map((a) => a.name || a.email).join(", ") || "(no recipients)";

function Row({ colour, office, title, detail, meta, actions, onOpen }: {
  colour?: string; office?: string; title: string; detail: string; meta: React.ReactNode; actions: React.ReactNode; onOpen: () => void;
}) {
  return (
    <li className="group flex items-center gap-3 px-3 py-3 hover:bg-background-gray-secondary_alt/40 sm:px-4">
      <button type="button" onClick={onOpen} className="flex min-w-0 flex-1 items-center gap-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 rounded-md">
        {colour && <span className="size-2 shrink-0 rounded-full" style={{ background: colour }} title={office} aria-hidden="true" />}
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-text-primary">{title}</span>
          <span className="block truncate text-xs text-text-tertiary">{office ? `${office} · ` : ""}{detail}</span>
        </span>
        <span className="shrink-0 text-xs text-text-secondary">{meta}</span>
      </button>
      <div className="flex shrink-0 gap-1">{actions}</div>
    </li>
  );
}

export function ScheduledPage() {
  const [scope] = useMailboxScope();
  const boxes = useMailboxSummaries();
  const scheduled = useScheduled();
  const client = useQueryClient();
  const [busy, setBusy] = useState<number | null>(null);
  const items = (scheduled.data ?? []).filter((item) => item.kind === "scheduled" && (scope === "all" || item.mailbox === scope));

  const cancel = async (id: number) => {
    setBusy(id);
    try {
      await cancelSend(id);
      toast("Scheduled send cancelled. The message is open as a draft.");
      client.invalidateQueries({ queryKey: mailKeys.scheduled() });
      client.invalidateQueries({ queryKey: mailKeys.drafts() });
    } catch (error) { toast.error(errorMessage(error)); } finally { setBusy(null); }
  };

  return (
    <Page>
      <PageHeader title="Scheduled" description="Messages waiting to be sent at a set time. Cancel one to edit it again." />
      {scheduled.isPending ? <TableSkeleton rows={4} columns={3} /> : scheduled.error ? (
        <RequestState loading={false} error={errorMessage(scheduled.error)} onRetry={() => scheduled.refetch()} />
      ) : items.length === 0 ? (
        <div className="rounded-xl border border-card-border bg-card-surface-area"><EmptyState icon={<ClockIcon />} title="Nothing scheduled" body="Use Schedule send in the compose window to send later." /></div>
      ) : (
        <ul className="divide-y divide-card-border overflow-hidden rounded-xl border border-card-border bg-card-surface-area">
          {items.map((item) => {
            const box = boxes.find((b) => b.id === item.mailbox);
            return (
              <Row key={item.id} colour={box?.colour} office={scope === "all" ? box?.office.name : undefined}
                title={item.subject || "(no subject)"} detail={`To: ${recipients(item.to)}`}
                meta={item.status === "failed" ? <StatusPill tone="error">Failed</StatusPill> : <span className="flex items-center gap-1.5"><ClockIcon size={14} />{dateTime(item.send_at)}</span>}
                onOpen={() => cancel(item.id)}
                actions={<Button size="sm" appearance="outline" isPending={busy === item.id} onPress={() => cancel(item.id)}>Cancel &amp; edit</Button>} />
            );
          })}
        </ul>
      )}
    </Page>
  );
}

export function DraftsPage() {
  const [scope] = useMailboxScope();
  const boxes = useMailboxSummaries();
  const drafts = useDrafts();
  const client = useQueryClient();
  const items = (drafts.data ?? []).filter((d) => scope === "all" || d.mailbox === scope);

  const discard = async (id: number) => {
    const previous = drafts.data;
    client.setQueryData(mailKeys.drafts(), previous?.filter((d) => d.id !== id));
    try { await mutate(`mail/drafts/${id}/`, "DELETE"); toast("Draft discarded."); }
    catch (error) { client.setQueryData(mailKeys.drafts(), previous); toast.error(errorMessage(error)); }
  };

  return (
    <Page>
      <PageHeader title="Drafts" description="Saved automatically while you write. Open one to keep going." />
      {drafts.isPending ? <TableSkeleton rows={4} columns={3} /> : drafts.error ? (
        <RequestState loading={false} error={errorMessage(drafts.error)} onRetry={() => drafts.refetch()} />
      ) : items.length === 0 ? (
        <div className="rounded-xl border border-card-border bg-card-surface-area"><EmptyState icon={<DraftIcon />} title="No drafts" body="Drafts are saved automatically while you write." /></div>
      ) : (
        <ul className="divide-y divide-card-border overflow-hidden rounded-xl border border-card-border bg-card-surface-area">
          {items.map((draft) => {
            const box = boxes.find((b) => b.id === draft.mailbox);
            return (
              <Row key={draft.id} colour={box?.colour} office={scope === "all" ? box?.office.name : undefined}
                title={draft.subject || "(no subject)"}
                detail={`${draft.to.length ? `To: ${recipients(draft.to)}` : "No recipients yet"}${draft.snippet ? ` — ${draft.snippet}` : ""}`}
                meta={<span className={cn("text-error-500")}>Draft · <span className="text-text-secondary">{listTime(draft.updated_at)}</span></span>}
                onOpen={() => openCompose({ mailbox: draft.mailbox, draftId: draft.id, to: draft.to, cc: draft.cc, bcc: draft.bcc, subject: draft.subject, html: draft.body_html, mode: draft.mode as "new", threadId: draft.thread ?? undefined, inReplyToMessage: draft.in_reply_to_message ?? undefined, attachmentIds: draft.attachment_ids })}
                actions={<Button size="sm" appearance="ghost" iconOnly aria-label="Discard draft" onPress={() => discard(draft.id)}><TrashIcon size={16} /></Button>} />
            );
          })}
        </ul>
      )}
    </Page>
  );
}
