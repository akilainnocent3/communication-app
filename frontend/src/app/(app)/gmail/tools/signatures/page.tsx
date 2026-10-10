"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { usePageTitle } from "@/components/shell/trail";
import { Button } from "@/components/tailgrids/core/button";
import { EmptyState } from "@/components/ui/empty-state";
import { SignatureIcon } from "@/components/ui/icons";
import { Page, PageHeader } from "@/components/ui/page";
import { RequestState, TableSkeleton } from "@/components/ui/request-state";
import { SectionCard } from "@/components/ui/section-card";
import { Chip } from "@/components/ui/status-pill";
import { errorMessage, mutate, request } from "@/services/api/client";
import type { SendAs } from "@/services/api/types";
import { mailKeys } from "@/platforms/gmail/api/keys";
import { RichTextField } from "@/platforms/gmail/compose/rich-text-field";
import { useToolMailbox } from "@/platforms/gmail/components/tool-mailbox";

export default function SignaturesPage() {
  usePageTitle({ page: "Signatures", section: "Tools" });
  const { mailbox, picker, empty } = useToolMailbox();
  const aliases = useQuery({ queryKey: mailKeys.sendAs(mailbox?.id ?? 0), queryFn: () => request<SendAs[]>(`mail/settings/${mailbox!.id}/signature/`), enabled: !!mailbox });

  return (
    <Page>
      <PageHeader title="Signatures" description="Added automatically to new messages and replies. Each “send as” address has its own." actions={picker} />
      {!mailbox ? empty : aliases.isPending ? <TableSkeleton rows={2} columns={1} /> : aliases.error ? (
        <RequestState loading={false} error={errorMessage(aliases.error)} onRetry={() => aliases.refetch()} />
      ) : aliases.data!.length === 0 ? (
        <SectionCard><EmptyState icon={<SignatureIcon />} title="No addresses" body="This mailbox has no send-as addresses." /></SectionCard>
      ) : (
        <div className="space-y-4">
          {aliases.data!.map((alias) => <SignatureCard key={`${mailbox.id}-${alias.email}`} mailboxId={mailbox.id} alias={alias} />)}
        </div>
      )}
    </Page>
  );
}

function SignatureCard({ mailboxId, alias }: { mailboxId: number; alias: SendAs }) {
  const client = useQueryClient();
  const [html, setHtml] = useState(alias.signature);
  const [busy, setBusy] = useState(false);
  const save = async () => {
    setBusy(true);
    try {
      await mutate(`mail/settings/${mailboxId}/signature/`, "PUT", { send_as: alias.email, signature: html });
      client.invalidateQueries({ queryKey: mailKeys.sendAs(mailboxId) });
      toast.success("Signature saved.");
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };
  return (
    <SectionCard title={<span className="flex flex-wrap items-center gap-2">{alias.display_name || alias.email}{alias.is_default && <Chip>Default</Chip>}</span>} description={alias.email}
      footer={<div className="flex justify-end"><Button onPress={save} isPending={busy} isDisabled={html === alias.signature}>Save signature</Button></div>}>
      <RichTextField label="Signature" initial={alias.signature} onChange={setHtml} placeholder="Kind regards, …" />
    </SectionCard>
  );
}
