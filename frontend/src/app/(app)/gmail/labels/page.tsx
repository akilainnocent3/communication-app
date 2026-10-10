"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Form } from "react-aria-components";
import { toast } from "sonner";
import { usePageTitle } from "@/components/shell/trail";
import { Button } from "@/components/tailgrids/core/button";
import { Dialog, DialogHeader, DialogTitle } from "@/components/tailgrids/core/dialog";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Field } from "@/components/ui/field";
import { ColourPicker } from "@/components/ui/form";
import { PencilIcon, PlusIcon, TagIcon, TrashIcon } from "@/components/ui/icons";
import { Page, PageHeader } from "@/components/ui/page";
import { RequestState, TableSkeleton } from "@/components/ui/request-state";
import { errorMessage, fieldError, mutate } from "@/services/api/client";
import type { Label } from "@/services/api/types";
import { mailKeys } from "@/platforms/gmail/api/keys";
import { useLabels } from "@/platforms/gmail/api/queries";
import { labelUrl } from "@/platforms/gmail/nav";
import { useToolMailbox } from "@/platforms/gmail/components/tool-mailbox";

export default function LabelsPage() {
  return <Suspense fallback={<Page><TableSkeleton /></Page>}><Labels /></Suspense>;
}

function Labels() {
  usePageTitle({ page: "Labels", section: "Tools" });
  const params = useSearchParams();
  const router = useRouter();
  const client = useQueryClient();
  const { mailbox, picker, empty } = useToolMailbox((box) => box.permissions.send);
  const labels = useLabels(mailbox?.id);
  const [editing, setEditing] = useState<Label | "new" | null>(params.get("new") ? "new" : null);
  const [deleting, setDeleting] = useState<Label | null>(null);
  const caps = mailbox?.provider === "imap_smtp" ? "Folders" : "Labels";

  const user = (labels.data ?? []).filter((label) => label.type === "user");
  const system = (labels.data ?? []).filter((label) => label.type !== "user" && !label.label_id.startsWith("CATEGORY_"));
  const close = () => { setEditing(null); if (params.get("new")) router.replace("/gmail/labels"); };

  return (
    <Page>
      <PageHeader title={caps} description={mailbox?.provider === "imap_smtp" ? "Folders on the mail server. Each folder works like a label." : "Organise conversations. A conversation can have several labels."}
        actions={<>{picker}{mailbox && <Button onPress={() => setEditing("new")}><PlusIcon size={16} />New label</Button>}</>} />
      {!mailbox ? empty : labels.isPending ? <TableSkeleton rows={5} columns={3} /> : labels.error ? (
        <RequestState loading={false} error={errorMessage(labels.error)} onRetry={() => labels.refetch()} />
      ) : (
        <div className="space-y-5">
          <section className="overflow-hidden rounded-xl border border-card-border bg-card-surface-area">
            <h2 className="border-b border-card-border px-4 py-3 text-sm font-semibold">Your labels</h2>
            {user.length === 0 ? (
              <EmptyState compact icon={<TagIcon />} title="No labels yet" body="Create labels like “Invoices” or “Urgent” to group conversations."
                action={<Button size="sm" onPress={() => setEditing("new")}><PlusIcon size={15} />New label</Button>} />
            ) : (
              <ul className="divide-y divide-card-border">
                {user.map((label) => (
                  <li key={label.id} className="flex items-center gap-3 px-4 py-2.5">
                    <span className="size-3 shrink-0 rounded-full" style={{ background: label.colour || "#9ca3af" }} aria-hidden="true" />
                    <Link href={labelUrl(label.label_id)} className="min-w-0 flex-1 truncate text-sm font-medium text-text-primary hover:text-primary-500">{label.name}</Link>
                    <span className="hidden text-xs tabular-nums text-text-tertiary sm:inline">{label.threads_total ?? 0} conversations{label.threads_unread ? ` · ${label.threads_unread} unread` : ""}</span>
                    <Button size="sm" appearance="ghost" iconOnly aria-label={`Edit ${label.name}`} onPress={() => setEditing(label)}><PencilIcon size={16} /></Button>
                    <Button size="sm" appearance="ghost" iconOnly aria-label={`Delete ${label.name}`} onPress={() => setDeleting(label)}><TrashIcon size={16} /></Button>
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section className="overflow-hidden rounded-xl border border-card-border bg-card-surface-area">
            <h2 className="border-b border-card-border px-4 py-3 text-sm font-semibold">System labels</h2>
            <ul className="grid divide-card-border sm:grid-cols-2">
              {system.map((label) => (
                <li key={label.id} className="flex items-center justify-between gap-3 border-b border-card-border px-4 py-2 text-sm">
                  <span className="truncate text-text-secondary">{label.name}</span>
                  <span className="text-xs tabular-nums text-text-tertiary">{label.threads_total ?? 0}</span>
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
      {mailbox && editing && (
        <LabelDialog mailboxId={mailbox.id} label={editing === "new" ? null : editing} onClose={close}
          onSaved={() => client.invalidateQueries({ queryKey: mailKeys.labels(mailbox.id) })} />
      )}
      <ConfirmDialog isOpen={!!deleting} onOpenChange={(open) => !open && setDeleting(null)} title={`Delete “${deleting?.name}”?`} confirmLabel="Delete label"
        body="The label is removed from every conversation. The conversations themselves are not deleted."
        onConfirm={async () => {
          if (!deleting || !mailbox) return;
          try { await mutate(`mail/labels/${deleting.id}/`, "DELETE"); toast("Label deleted."); client.invalidateQueries({ queryKey: mailKeys.labels(mailbox.id) }); client.invalidateQueries({ queryKey: mailKeys.threadLists() }); }
          catch (e) { toast.error(errorMessage(e)); throw e; }
        }} />
    </Page>
  );
}

function LabelDialog({ mailboxId, label, onClose, onSaved }: { mailboxId: number; label: Label | null; onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState(label?.name ?? "");
  const [colour, setColour] = useState(label?.colour || "#3758f9");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const submit = async () => {
    setBusy(true); setError(null);
    try {
      if (label) await mutate(`mail/labels/${label.id}/`, "PATCH", { name, colour });
      else await mutate("mail/labels/", "POST", { mailbox: mailboxId, name, colour });
      toast.success(label ? "Label updated." : `Label “${name}” created.`);
      onSaved(); onClose();
    } catch (e) { setError(e); } finally { setBusy(false); }
  };
  return (
    <Dialog isOpen onOpenChange={(open) => !open && onClose()} className="max-w-md">
      <DialogHeader><DialogTitle>{label ? "Edit label" : "New label"}</DialogTitle></DialogHeader>
      <Form className="mt-4 space-y-4" onSubmit={(e) => { e.preventDefault(); submit(); }}>
        <Field label="Name" value={name} onChange={setName} isRequired autoFocus error={fieldError(error, "name")} hint="Use / to nest, e.g. Clients/Arusha" />
        <ColourPicker label="Colour" value={colour} onChange={setColour} />
        {!!error && !fieldError(error, "name") && <p role="alert" className="text-sm text-error-500">{errorMessage(error)}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <Button appearance="outline" onPress={onClose}>Cancel</Button>
          <Button type="submit" isPending={busy} isDisabled={!name.trim()}>{label ? "Save" : "Create"}</Button>
        </div>
      </Form>
    </Dialog>
  );
}
