"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { useSession, ME_KEY } from "@/components/shell/session-provider";
import { usePageTitle } from "@/components/shell/trail";
import { Button } from "@/components/tailgrids/core/button";
import { ButtonLink } from "@/components/tailgrids/core/button-link";
import { EmptyState } from "@/components/ui/empty-state";
import { InboxIcon, PlusIcon, RefreshIcon, SearchIcon } from "@/components/ui/icons";
import { Page, PageHeader } from "@/components/ui/page";
import { PageSkeleton, RequestState } from "@/components/ui/request-state";
import { cardClass } from "@/components/ui/section-card";
import { ago } from "@/lib/format";
import { errorMessage, mutate } from "@/services/api/client";
import type { Mailbox } from "@/services/api/types";
import { mailKeys } from "@/platforms/gmail/api/keys";
import { useMailboxes } from "@/platforms/gmail/api/queries";
import { MailboxAvatar, MailboxStatus, ProviderBadge } from "@/platforms/gmail/components/mailbox-badges";
import { ConnectLinkDialog } from "@/platforms/gmail/components/mailboxes/connect-link-dialog";
import { setMailboxScope } from "@/platforms/gmail/state";
import { cn } from "@/utils/cn";

export default function MailboxesPage() {
  usePageTitle({ page: "Connected mailboxes", section: "Mailboxes" });
  const { can } = useSession();
  const mailboxes = useMailboxes();
  const [query, setQuery] = useState("");
  const [link, setLink] = useState<Mailbox | null>(null);
  const canAdd = can("mail.manage_mailboxes");

  const items = (mailboxes.data ?? []).filter((box) => {
    const q = query.trim().toLowerCase();
    return !q || [box.email, box.name, box.office.name].some((v) => v.toLowerCase().includes(q));
  });

  return (
    <Page wide>
      <PageHeader title="Connected mailboxes" description="Every office mailbox this workspace can read and send from."
        actions={canAdd && <ButtonLink href="/gmail/mailboxes/new"><PlusIcon size={16} />Add mailbox</ButtonLink>} />
      {mailboxes.isPending ? <PageSkeleton /> : mailboxes.error ? (
        <RequestState loading={false} error={errorMessage(mailboxes.error)} onRetry={() => mailboxes.refetch()} />
      ) : mailboxes.data!.length === 0 ? (
        <div className={cardClass()}>
          <EmptyState icon={<InboxIcon />} title="No mailboxes yet" body="Connect your first office in under a minute. Staff only open a link and tap Allow."
            action={canAdd ? <ButtonLink href="/gmail/mailboxes/new"><PlusIcon size={16} />Add your first mailbox</ButtonLink> : undefined} />
        </div>
      ) : (
        <>
          {mailboxes.data!.length > 6 && (
            <label className="relative mb-4 block max-w-sm">
              <span className="sr-only">Filter mailboxes</span>
              <SearchIcon size={16} className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-icon-tertiary" />
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Filter by office or email"
                className="h-10 w-full rounded-lg border border-card-border bg-input-background pr-3 pl-9 text-sm text-text-primary outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-500/20" />
            </label>
          )}
          <ul className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
            {items.map((box) => <MailboxCard key={box.id} box={box} onSendLink={() => setLink(box)} />)}
          </ul>
          {items.length === 0 && <p className="py-10 text-center text-sm text-text-tertiary">No mailbox matches “{query}”.</p>}
        </>
      )}
      {link && <ConnectLinkDialog mailboxId={link.id} email={link.email} isOpen reconnect={link.status !== "pending"} onOpenChange={(open) => !open && setLink(null)} />}
    </Page>
  );
}

function MailboxCard({ box, onSendLink }: { box: Mailbox; onSendLink: () => void }) {
  const router = useRouter();
  const client = useQueryClient();
  const sync = useMutation({
    mutationFn: () => mutate(`mail/mailboxes/${box.id}/sync/`, "POST"),
    onSuccess: () => { toast.success(`Syncing ${box.email}…`); client.invalidateQueries({ queryKey: mailKeys.mailboxes() }); client.invalidateQueries({ queryKey: ME_KEY }); },
    onError: (error) => toast.error(errorMessage(error)),
  });
  const google = box.provider === "gmail_oauth";
  const attention = box.status === "needs_reconnect" || box.status === "error";
  const waiting = box.status === "pending" || box.status === "disabled";

  return (
    <li className={cn(cardClass({ interactive: true }), "flex flex-col gap-4", attention && "border-warning-500/50")}>
      <div className="flex min-w-0 items-start gap-3">
        <MailboxAvatar name={box.name} colour={box.colour ?? ""} size={40} />
        <div className="min-w-0 flex-1">
          <Link href={`/gmail/mailboxes/${box.id}`} className="block truncate font-semibold text-text-primary hover:text-primary-500 hover:underline">{box.office.name}</Link>
          <p className="truncate text-sm text-text-tertiary" title={box.email}>{box.email}</p>
        </div>
        <ProviderBadge provider={box.provider} />
      </div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-text-tertiary">
        <MailboxStatus status={box.status ?? "pending"} progress={box.sync_progress} />
        {box.last_synced_at && <span>Synced {ago(box.last_synced_at)}</span>}
        {box.status === "connected" && <span className="tabular-nums">{box.unread} unread</span>}
      </div>
      {box.sync_error && attention && <p className="line-clamp-2 text-xs text-warning-700 dark:text-warning-300">{box.sync_error}</p>}
      <div className="mt-auto flex flex-wrap gap-2 border-t border-card-border pt-3">
        {!waiting && box.permissions.read && (
          <Button size="sm" appearance="outline" onPress={() => { setMailboxScope(box.id); router.push("/gmail/inbox"); }}><InboxIcon size={15} />Open</Button>
        )}
        {box.permissions.manage && !waiting && !attention && (
          <Button size="sm" appearance="ghost" onPress={() => sync.mutate()} isPending={sync.isPending}><RefreshIcon size={15} />Sync now</Button>
        )}
        {box.permissions.manage && google && (waiting || attention) && (
          <Button size="sm" onPress={onSendLink}>{waiting ? "Send connect link" : "Send reconnect link"}</Button>
        )}
        {box.permissions.manage && !google && (waiting || attention) && (
          <ButtonLink size="sm" href={`/gmail/mailboxes/${box.id}`}>Fix settings</ButtonLink>
        )}
        {box.permissions.manage && <ButtonLink size="sm" appearance="ghost" href={`/gmail/mailboxes/${box.id}`} className="ml-auto">Manage</ButtonLink>}
      </div>
    </li>
  );
}
