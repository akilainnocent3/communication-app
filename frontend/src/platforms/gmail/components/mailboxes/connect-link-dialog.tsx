"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import DOMPurify from "dompurify";
import { useEffect } from "react";
import { toast } from "sonner";
import { Button } from "@/components/tailgrids/core/button";
import { Dialog, DialogHeader, DialogTitle } from "@/components/tailgrids/core/dialog";
import { ActivityIndicator } from "@/components/ui/activity-indicator";
import { CheckCircleIcon, CopyIcon, WhatsappIcon } from "@/components/ui/icons";
import { RequestState } from "@/components/ui/request-state";
import { ME_KEY } from "@/components/shell/session-provider";
import { dateTime } from "@/lib/format";
import { errorMessage, mutate, request } from "@/services/api/client";
import type { InviteCreated, MailboxStatus } from "@/services/api/types";
import { mailKeys } from "../../api/keys";

/**
 * "Send connect link": creates a single-use 72 h invite and shows Copy, WhatsApp and a QR code, with the live
 * status (Waiting → Connected ✓) polled every 5 s while the dialog is open.
 */
export function ConnectLinkDialog({ mailboxId, email, isOpen, onOpenChange, reconnect = false }: {
  mailboxId: number; email: string; isOpen: boolean; onOpenChange: (open: boolean) => void; reconnect?: boolean;
}) {
  const client = useQueryClient();
  const create = useMutation({
    mutationFn: () => mutate<InviteCreated>(`mail/mailboxes/${mailboxId}/invites/`, "POST"),
    onSuccess: () => client.invalidateQueries({ queryKey: mailKeys.invites(mailboxId) }),
  });
  const invite = isOpen ? create.data ?? null : null;
  const { mutate: createInvite, reset } = create;
  // Each opening creates a fresh single-use link; closing forgets it.
  useEffect(() => {
    if (!isOpen) return;
    createInvite();
    return () => reset();
  }, [isOpen, createInvite, reset]);

  const status = useQuery({
    queryKey: mailKeys.status(mailboxId),
    queryFn: () => request<MailboxStatus>(`mail/mailboxes/${mailboxId}/status/`),
    enabled: isOpen && !!invite,
    refetchInterval: (q) => (q.state.data?.latest_invite?.state === "used" ? false : 5000),
  });
  const connected = !!invite && status.data?.latest_invite?.id === invite.id && status.data.latest_invite.state === "used";
  useEffect(() => {
    if (!connected) return;
    client.invalidateQueries({ queryKey: mailKeys.mailboxes() });
    client.invalidateQueries({ queryKey: ME_KEY });
  }, [connected, client]);

  const copy = async () => {
    if (!invite) return;
    try { await navigator.clipboard.writeText(invite.url); toast.success("Link copied. Paste it in a message to the office."); }
    catch { toast.error("Couldn't copy automatically. Select the link and copy it."); }
  };

  return (
    <Dialog isOpen={isOpen} onOpenChange={onOpenChange} className="max-w-lg">
      <DialogHeader><DialogTitle>{reconnect ? "Send a reconnect link" : "Send a connect link"}</DialogTitle></DialogHeader>
      <p className="mt-1 text-sm text-text-tertiary">Send this to the person who uses <span className="font-medium text-text-primary">{email}</span>. They open it, choose the account and tap Allow. No passwords are shared.</p>

      {create.isPending && <div className="flex justify-center py-12"><ActivityIndicator label="Creating link" /></div>}
      {create.error && <div className="mt-5"><RequestState loading={false} error={errorMessage(create.error)} onRetry={() => create.mutate()} /></div>}

      {invite && (
        <div className="mt-5 space-y-5 animate-fade-up">
          <div className="flex flex-col items-center gap-5 sm:flex-row sm:items-start">
            <div className="shrink-0 rounded-xl border border-card-border bg-white p-2.5 [&_svg]:size-36" aria-label="QR code for the connect link" role="img"
              dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(invite.qr_svg, { USE_PROFILES: { svg: true } }) }} />
            <div className="w-full min-w-0 space-y-3">
              <label className="block text-xs font-medium text-text-secondary" htmlFor="connect-url">Connect link</label>
              <div className="flex gap-2">
                <input id="connect-url" readOnly value={invite.url} onFocus={(event) => event.currentTarget.select()}
                  className="h-10 min-w-0 flex-1 rounded-lg border border-card-border bg-background-gray-secondary_alt/50 px-3 font-mono text-xs text-text-primary focus:border-primary-500 focus:outline-none" />
                <Button appearance="outline" onPress={copy} aria-label="Copy link"><CopyIcon size={16} />Copy</Button>
              </div>
              <a href={invite.whatsapp_url} target="_blank" rel="noopener noreferrer"
                className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-[#25D366] px-4 text-sm font-semibold text-[#06301a] transition hover:brightness-95 focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none">
                <WhatsappIcon size={18} /> Share on WhatsApp
              </a>
              <p className="text-xs text-text-tertiary">Works once · expires {dateTime(invite.expires_at)}</p>
            </div>
          </div>

          <div role="status" aria-live="polite" className={connected ? "flex items-center gap-3 rounded-xl border border-success-500/40 bg-success-500/10 px-4 py-3" : "flex items-center gap-3 rounded-xl border border-card-border bg-background-gray-secondary_alt/40 px-4 py-3"}>
            {connected ? <CheckCircleIcon className="text-success-500" /> : <ActivityIndicator size="sm" decorative />}
            <span className="text-sm font-medium text-text-primary">{connected ? "Connected ✓ The inbox is syncing now." : "Waiting for the office to connect…"}</span>
          </div>
        </div>
      )}
      <div className="mt-6 flex justify-end"><Button appearance={connected ? "fill" : "outline"} onPress={() => onOpenChange(false)}>{connected ? "Done" : "Close"}</Button></div>
    </Dialog>
  );
}
