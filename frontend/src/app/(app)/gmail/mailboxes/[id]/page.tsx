"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { toast } from "sonner";
import { ME_KEY } from "@/components/shell/session-provider";
import { usePageTitle } from "@/components/shell/trail";
import { Button } from "@/components/tailgrids/core/button";
import { ButtonLink } from "@/components/tailgrids/core/button-link";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Field } from "@/components/ui/field";
import { ColourPicker, SelectField } from "@/components/ui/form";
import { ArrowLeftIcon, CheckCircleIcon, ErrorIcon, GoogleIcon, InboxIcon, LinkIcon, RefreshIcon, WarningIcon } from "@/components/ui/icons";
import { Page } from "@/components/ui/page";
import { PageSkeleton, RequestState } from "@/components/ui/request-state";
import { SectionCard } from "@/components/ui/section-card";
import { StatusPill } from "@/components/ui/status-pill";
import { ago, dateTime } from "@/lib/format";
import { errorMessage, mutate, request } from "@/services/api/client";
import type { Detection, Invite, Mailbox, Office } from "@/services/api/types";
import { mailKeys } from "@/platforms/gmail/api/keys";
import { useMailbox } from "@/platforms/gmail/api/queries";
import { MailboxAvatar, MailboxStatus, ProviderBadge } from "@/platforms/gmail/components/mailbox-badges";
import { AccessManager } from "@/platforms/gmail/components/mailboxes/access-manager";
import { ConnectLinkDialog } from "@/platforms/gmail/components/mailboxes/connect-link-dialog";
import { connectResult } from "@/platforms/gmail/components/mailboxes/connect-results";
import { ImapForm } from "@/platforms/gmail/components/mailboxes/imap-form";
import { setMailboxScope } from "@/platforms/gmail/state";
import { cn } from "@/utils/cn";

export default function MailboxDetailPage() {
  return <Suspense fallback={<Page><PageSkeleton /></Page>}><Detail /></Suspense>;
}

function Detail() {
  const { id } = useParams<{ id: string }>();
  const mailboxId = Number(id);
  const params = useSearchParams();
  const router = useRouter();
  const client = useQueryClient();
  const mailbox = useMailbox(mailboxId);
  const box = mailbox.data;
  usePageTitle({ page: "Mailbox", section: "Mailboxes", detail: box?.email });

  // Poll while syncing so the progress pill moves.
  const syncing = box?.status === "syncing";
  useEffect(() => {
    if (!syncing) return;
    const timer = window.setInterval(() => client.invalidateQueries({ queryKey: mailKeys.mailbox(mailboxId) }), 4000);
    return () => window.clearInterval(timer);
  }, [syncing, client, mailboxId]);

  const refresh = () => {
    client.invalidateQueries({ queryKey: mailKeys.mailbox(mailboxId) });
    client.invalidateQueries({ queryKey: mailKeys.mailboxes() });
    client.invalidateQueries({ queryKey: ME_KEY });
  };

  if (mailbox.isPending) return <Page><PageSkeleton /></Page>;
  if (mailbox.error || !box) return <Page><RequestState loading={false} error={errorMessage(mailbox.error)} onRetry={() => mailbox.refetch()} /></Page>;
  const result = connectResult(params.get("result"), params, box.email);

  return (
    <Page className="max-w-4xl">
      <ButtonLink href="/gmail/mailboxes" appearance="ghost" size="sm" className="mb-3 -ml-2"><ArrowLeftIcon size={16} />All mailboxes</ButtonLink>
      {result && (
        <div role="status" className={cn("mb-4 flex items-start gap-3 rounded-xl border p-4 text-sm",
          result.tone === "success" ? "border-success-500/40 bg-success-500/10" : result.tone === "warning" ? "border-warning-500/40 bg-warning-500/10" : "border-error-500/40 bg-error-500/10")}>
          {result.tone === "success" ? <CheckCircleIcon className="shrink-0 text-success-500" /> : result.tone === "warning" ? <WarningIcon className="shrink-0 text-warning-500" /> : <ErrorIcon className="shrink-0 text-error-500" />}
          <div className="min-w-0 flex-1"><p className="font-semibold text-text-primary">{result.title}</p><p className="mt-0.5 text-text-secondary">{result.body}</p></div>
          <button type="button" className="text-xs font-medium text-text-tertiary hover:text-text-primary" onClick={() => router.replace(`/gmail/mailboxes/${box.id}`)}>Dismiss</button>
        </div>
      )}

      <header className="mb-5 flex flex-wrap items-start gap-4">
        <MailboxAvatar name={box.name} colour={box.colour ?? ""} size={52} />
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-xl font-semibold text-text-primary sm:text-2xl">{box.office.name}</h1>
          <p className="truncate text-sm text-text-tertiary">{box.email}{box.display_name ? ` · ${box.display_name}` : ""}</p>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-text-tertiary">
            <MailboxStatus status={box.status ?? "pending"} progress={box.sync_progress} />
            <ProviderBadge provider={box.provider} />
            {box.last_synced_at && <span>Last sync {ago(box.last_synced_at)}</span>}
            {box.connected_at && <span>Connected {dateTime(box.connected_at)}{box.connected_by ? ` by ${box.connected_by}` : ""}</span>}
          </div>
        </div>
        {(box.status === "connected" || box.status === "syncing") && (
          <Button appearance="outline" onPress={() => { setMailboxScope(box.id); router.push("/gmail/inbox"); }}><InboxIcon size={16} />Open inbox</Button>
        )}
      </header>

      <div className="space-y-4 sm:space-y-5">
        <Connection box={box} onChanged={refresh} />
        {box.permissions.manage && <DetailsForm box={box} onSaved={refresh} />}
        {box.permissions.manage && <AccessManager mailboxId={box.id} />}
        {box.permissions.manage && <DangerZone box={box} onChanged={refresh} />}
      </div>
    </Page>
  );
}

function Connection({ box, onChanged }: { box: Mailbox; onChanged: () => void }) {
  const [linkOpen, setLinkOpen] = useState(false);
  const google = box.provider === "gmail_oauth";
  const healthy = box.status === "connected" || box.status === "syncing";
  const invites = useQuery({ queryKey: mailKeys.invites(box.id), queryFn: () => request<Invite[]>(`mail/mailboxes/${box.id}/invites/`), enabled: google && box.permissions.manage });
  const detect = useQuery({ queryKey: ["mail", "detect", box.id], queryFn: () => mutate<Detection>(`mail/mailboxes/${box.id}/detect/`, "POST"), enabled: box.provider === "imap_smtp" && !healthy, staleTime: Infinity });
  const sync = useMutation({ mutationFn: () => mutate(`mail/mailboxes/${box.id}/sync/`, "POST"), onSuccess: () => { toast.success("Sync started."); onChanged(); }, onError: (e) => toast.error(errorMessage(e)) });
  const connectNow = useMutation({
    mutationFn: () => mutate<{ url: string }>(`mail/mailboxes/${box.id}/connect/`, "POST"),
    onSuccess: ({ url }) => window.location.assign(url),
    onError: (e) => toast.error(errorMessage(e)),
  });
  const client = useQueryClient();
  const revoke = async (invite: Invite) => {
    try { await mutate(`mail/mailboxes/${box.id}/invites/${invite.id}/revoke/`, "POST"); toast("Link revoked. It no longer works."); client.invalidateQueries({ queryKey: mailKeys.invites(box.id) }); }
    catch (e) { toast.error(errorMessage(e)); }
  };

  return (
    <SectionCard title="Connection" description={google ? "Google sign-in (OAuth). Tokens are stored encrypted." : box.provider === "imap_smtp" ? "Email server (IMAP/SMTP)." : box.provider === "workspace_delegation" ? "Company Google Workspace, no sign-in needed." : "Demo mailbox with sample data."}
      actions={box.permissions.manage && healthy && <Button size="sm" appearance="outline" onPress={() => sync.mutate()} isPending={sync.isPending}><RefreshIcon size={15} />Sync now</Button>}>
      {box.sync_error && !healthy && <p className="mb-4 rounded-lg border border-warning-500/40 bg-warning-500/10 p-3 text-sm text-text-primary">{box.sync_error}</p>}

      {google && box.permissions.manage && (
        <>
          <div className="flex flex-wrap gap-2">
            <Button onPress={() => setLinkOpen(true)}><LinkIcon size={16} />{healthy ? "Send reconnect link" : box.status === "pending" ? "Send connect link" : "Send reconnect link"}</Button>
            <Button appearance="outline" onPress={() => connectNow.mutate()} isPending={connectNow.isPending}><GoogleIcon size={16} />{healthy ? "Reconnect now" : "Connect now"}</Button>
          </div>
          {invites.data && invites.data.length > 0 && (
            <div className="mt-5">
              <h3 className="mb-2 text-xs font-semibold tracking-wide text-text-tertiary uppercase">Recent connect links</h3>
              <ul className="divide-y divide-card-border rounded-lg border border-card-border">
                {invites.data.slice(0, 6).map((invite) => (
                  <li key={invite.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2.5 text-sm">
                    <InviteState state={invite.state} />
                    <span className="min-w-0 flex-1 truncate text-text-secondary">Created {dateTime(invite.created_at)}{invite.created_by ? ` by ${invite.created_by}` : ""}</span>
                    <span className="text-xs text-text-tertiary">{invite.used_at ? `Used ${dateTime(invite.used_at)}` : invite.state === "active" ? `Expires ${dateTime(invite.expires_at)}` : ""}</span>
                    {invite.state === "active" && <Button size="sm" appearance="ghost" onPress={() => revoke(invite)}>Revoke</Button>}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <ConnectLinkDialog mailboxId={box.id} email={box.email} isOpen={linkOpen} onOpenChange={setLinkOpen} reconnect={box.status !== "pending"} />
        </>
      )}

      {box.provider === "imap_smtp" && box.permissions.manage && (
        healthy ? <p className="text-sm text-text-secondary">Connected with the server settings. To change the password, disconnect and connect again.</p>
          : detect.isPending ? <p className="text-sm text-text-tertiary">Detecting server settings…</p>
            : <ImapForm mailboxId={box.id} email={box.email} defaults={detect.data?.imap_defaults} onSaved={onChanged} />
      )}

      {!box.permissions.manage && <p className="text-sm text-text-tertiary">Only people who manage this mailbox can change its connection.</p>}
      {box.provider === "workspace_delegation" && box.permissions.manage && !healthy && (
        <Button onPress={() => connectNow.mutate()} isPending={connectNow.isPending}>Connect</Button>
      )}
    </SectionCard>
  );
}

function InviteState({ state }: { state: string }) {
  if (state === "used") return <StatusPill tone="success">Used</StatusPill>;
  if (state === "active") return <StatusPill tone="info">Active</StatusPill>;
  if (state === "revoked") return <StatusPill tone="neutral">Revoked</StatusPill>;
  return <StatusPill tone="neutral">Expired</StatusPill>;
}

function DetailsForm({ box, onSaved }: { box: Mailbox; onSaved: () => void }) {
  const offices = useQuery({ queryKey: ["settings", "offices"], queryFn: () => request<Office[]>("settings/offices/"), staleTime: 60_000 });
  const [office, setOffice] = useState(String(box.office.id));
  const [name, setName] = useState(box.display_name ?? "");
  const [colour, setColour] = useState(box.colour ?? "#3758f9");
  const save = useMutation({
    mutationFn: () => mutate<Mailbox>(`mail/mailboxes/${box.id}/`, "PATCH", { office: Number(office), display_name: name, colour }),
    onSuccess: () => { toast.success("Mailbox updated."); onSaved(); },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const dirty = office !== String(box.office.id) || name !== (box.display_name ?? "") || colour !== (box.colour ?? "");
  return (
    <SectionCard title="Details" description="How this mailbox appears in the switcher and the unified inbox."
      footer={<div className="flex justify-end"><Button onPress={() => save.mutate()} isPending={save.isPending} isDisabled={!dirty}>Save changes</Button></div>}>
      <div className="grid gap-4 sm:grid-cols-2">
        <SelectField label="Office" value={office} onChange={(e) => setOffice(e.target.value)} options={(offices.data ?? [box.office]).map((o) => ({ value: String(o.id), label: o.name }))} />
        <Field label="Display name" value={name} onChange={setName} placeholder={box.email} />
        <div className="sm:col-span-2"><ColourPicker label="Colour" value={colour} onChange={setColour} /></div>
      </div>
    </SectionCard>
  );
}

function DangerZone({ box, onChanged }: { box: Mailbox; onChanged: () => void }) {
  const router = useRouter();
  const client = useQueryClient();
  const [confirm, setConfirm] = useState<"disconnect" | "delete" | null>(null);
  const connected = box.status !== "pending";
  return (
    <SectionCard tone="danger" title="Disconnect or remove" description="Disconnecting revokes access at Google (or forgets the password) and removes the synced copy of the mail.">
      <div className="flex flex-wrap gap-2">
        {connected && <Button variant="danger" appearance="outline" onPress={() => setConfirm("disconnect")}>Disconnect</Button>}
        <Button variant="danger" appearance="ghost" onPress={() => setConfirm("delete")}>Remove mailbox</Button>
      </div>
      <ConfirmDialog isOpen={confirm === "disconnect"} onOpenChange={(open) => !open && setConfirm(null)} title={`Disconnect ${box.email}?`} confirmLabel="Disconnect"
        body="Access is revoked and synced mail is removed from this workspace. The mail stays in the real mailbox. You can reconnect later."
        onConfirm={async () => { try { await mutate(`mail/mailboxes/${box.id}/disconnect/`, "POST"); toast("Mailbox disconnected."); onChanged(); } catch (e) { toast.error(errorMessage(e)); throw e; } }} />
      <ConfirmDialog isOpen={confirm === "delete"} onOpenChange={(open) => !open && setConfirm(null)} title={`Remove ${box.email}?`} confirmLabel="Remove mailbox"
        body="The mailbox, its access list and connect links are removed from this workspace. The real mailbox is not affected."
        onConfirm={async () => {
          try {
            await mutate(`mail/mailboxes/${box.id}/`, "DELETE");
            toast("Mailbox removed.");
            client.invalidateQueries({ queryKey: mailKeys.mailboxes() });
            client.invalidateQueries({ queryKey: ME_KEY });
            router.replace("/gmail/mailboxes");
          } catch (e) { toast.error(errorMessage(e)); throw e; }
        }} />
    </SectionCard>
  );
}
