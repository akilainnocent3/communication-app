"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Form } from "react-aria-components";
import { toast } from "sonner";
import { usePageTitle } from "@/components/shell/trail";
import { Button } from "@/components/tailgrids/core/button";
import { Dialog, DialogHeader, DialogTitle } from "@/components/tailgrids/core/dialog";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Field } from "@/components/ui/field";
import { SelectField } from "@/components/ui/form";
import { FilterIcon, PlusIcon, ShieldIcon, TrashIcon } from "@/components/ui/icons";
import { Page, PageHeader } from "@/components/ui/page";
import { RequestState, TableSkeleton } from "@/components/ui/request-state";
import { SectionCard } from "@/components/ui/section-card";
import { errorMessage, mutate, request } from "@/services/api/client";
import type { Filter, Label } from "@/services/api/types";
import { mailKeys } from "@/platforms/gmail/api/keys";
import { useLabels, useMailboxes } from "@/platforms/gmail/api/queries";
import { useToolMailbox } from "@/platforms/gmail/components/tool-mailbox";

/** Checkbox actions and the label changes they stand for (Gmail filter semantics). */
const ACTIONS = [
  { key: "skip_inbox", label: "Skip the inbox (archive it)", remove: "INBOX" },
  { key: "mark_read", label: "Mark as read", remove: "UNREAD" },
  { key: "star", label: "Star it", add: "STARRED" },
  { key: "important", label: "Always mark as important", add: "IMPORTANT" },
  { key: "never_spam", label: "Never send it to spam", remove: "SPAM" },
  { key: "delete", label: "Delete it", add: "TRASH" },
] as const;

function describe(filter: Filter, labels: Label[]) {
  const c = filter.criteria;
  const when = [c.from && `from ${c.from}`, c.to && `to ${c.to}`, c.subject && `subject has “${c.subject}”`, c.query && `contains “${c.query}”`, c.hasAttachment && "has an attachment"].filter(Boolean).join(", ");
  const name = (id: string) => labels.find((l) => l.label_id === id)?.name ?? id;
  const a = filter.action;
  const then = [
    ...ACTIONS.filter((x) => ("add" in x && a.addLabelIds?.includes(x.add)) || ("remove" in x && a.removeLabelIds?.includes(x.remove))).map((x) => x.label.toLowerCase()),
    ...(a.addLabelIds ?? []).filter((id) => !ACTIONS.some((x) => "add" in x && x.add === id)).map((id) => `apply label “${name(id)}”`),
    a.forward && `forward to ${a.forward}`,
  ].filter(Boolean).join(", ");
  return { when: when || "any message", then: then || "no action" };
}

export default function FiltersPage() {
  usePageTitle({ page: "Filters & rules", section: "Tools" });
  const { mailbox, picker, empty } = useToolMailbox();
  const mailboxes = useMailboxes();
  const caps = mailboxes.data?.find((box) => box.id === mailbox?.id)?.capabilities;
  const client = useQueryClient();
  const filters = useQuery({ queryKey: mailKeys.filters(mailbox?.id ?? 0), queryFn: () => request<Filter[]>(`mail/settings/${mailbox!.id}/filters/`), enabled: !!mailbox && caps?.filters !== false });
  const labels = useLabels(mailbox?.id);
  const [creating, setCreating] = useState<null | "filter" | "block">(null);
  const [deleting, setDeleting] = useState<Filter | null>(null);

  return (
    <Page>
      <PageHeader title="Filters & rules" description="Handle incoming mail automatically: label it, archive it, forward it or block a sender."
        actions={<>{picker}{mailbox && caps?.filters !== false && <><Button appearance="outline" onPress={() => setCreating("block")}><ShieldIcon size={16} />Block sender</Button><Button onPress={() => setCreating("filter")}><PlusIcon size={16} />New filter</Button></>}</>} />
      {!mailbox ? empty : caps && !caps.filters ? (
        <SectionCard><EmptyState icon={<FilterIcon />} title="Not available for this mailbox" body="Filters are a Gmail feature. Mailboxes on other mail servers manage rules in their own webmail." /></SectionCard>
      ) : filters.isPending ? <TableSkeleton rows={3} columns={2} /> : filters.error ? (
        <RequestState loading={false} error={errorMessage(filters.error)} onRetry={() => filters.refetch()} />
      ) : filters.data!.length === 0 ? (
        <SectionCard><EmptyState icon={<FilterIcon />} title="No filters yet" body="For example: put every message from your bank under the label “Bank” and skip the inbox."
          action={<Button onPress={() => setCreating("filter")}><PlusIcon size={16} />Create a filter</Button>} /></SectionCard>
      ) : (
        <ul className="divide-y divide-card-border overflow-hidden rounded-xl border border-card-border bg-card-surface-area">
          {filters.data!.map((filter) => {
            const text = describe(filter, labels.data ?? []);
            return (
              <li key={filter.id} className="flex items-start gap-3 px-4 py-3">
                <FilterIcon size={18} className="mt-0.5 shrink-0 text-icon-tertiary" />
                <p className="min-w-0 flex-1 text-sm"><span className="text-text-tertiary">When </span><span className="font-medium text-text-primary">{text.when}</span><span className="text-text-tertiary"> → </span><span className="text-text-secondary">{text.then}</span></p>
                <Button size="sm" appearance="ghost" iconOnly aria-label="Delete filter" onPress={() => setDeleting(filter)}><TrashIcon size={16} /></Button>
              </li>
            );
          })}
        </ul>
      )}
      {mailbox && creating && (
        <FilterDialog mailboxId={mailbox.id} block={creating === "block"} labels={(labels.data ?? []).filter((l) => l.type === "user")} onClose={() => setCreating(null)}
          onSaved={() => client.invalidateQueries({ queryKey: mailKeys.filters(mailbox.id) })} />
      )}
      <ConfirmDialog isOpen={!!deleting} onOpenChange={(open) => !open && setDeleting(null)} title="Delete this filter?" confirmLabel="Delete filter" body="New mail will no longer be handled by it. Mail already filtered is not changed."
        onConfirm={async () => {
          if (!deleting || !mailbox) return;
          try { await mutate(`mail/settings/${mailbox.id}/filters/${encodeURIComponent(deleting.id)}/`, "DELETE"); toast("Filter deleted."); client.invalidateQueries({ queryKey: mailKeys.filters(mailbox.id) }); }
          catch (e) { toast.error(errorMessage(e)); throw e; }
        }} />
    </Page>
  );
}

function FilterDialog({ mailboxId, block, labels, onClose, onSaved }: { mailboxId: number; block: boolean; labels: Label[]; onClose: () => void; onSaved: () => void }) {
  const [criteria, setCriteria] = useState({ from: "", to: "", subject: "", query: "", hasAttachment: false });
  const [checked, setChecked] = useState<Set<string>>(new Set(block ? ["delete"] : []));
  const [label, setLabel] = useState("");
  const [forward, setForward] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    setBusy(true); setError("");
    const add: string[] = [], remove: string[] = [];
    for (const action of ACTIONS) {
      if (!checked.has(action.key)) continue;
      if ("add" in action) add.push(action.add); else remove.push(action.remove);
    }
    if (label) add.push(label);
    try {
      await mutate(`mail/settings/${mailboxId}/filters/`, "POST", { criteria, action: { addLabelIds: add, removeLabelIds: remove, forward } });
      toast.success(block ? `Mail from ${criteria.from} will go straight to Trash.` : "Filter created.");
      onSaved(); onClose();
    } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  };

  return (
    <Dialog isOpen onOpenChange={(open) => !open && onClose()} className="max-w-lg">
      <DialogHeader><DialogTitle>{block ? "Block a sender" : "New filter"}</DialogTitle></DialogHeader>
      <Form className="mt-4 space-y-4" onSubmit={(e) => { e.preventDefault(); submit(); }}>
        {block ? (
          <>
            <Field label="Sender email or domain" value={criteria.from} onChange={(from) => setCriteria((c) => ({ ...c, from }))} isRequired autoFocus placeholder="spam@example.com" />
            <p className="text-sm text-text-tertiary">Future messages from this sender go straight to Trash.</p>
          </>
        ) : (
          <>
            <fieldset className="space-y-3">
              <legend className="mb-1 text-xs font-semibold tracking-wide text-text-tertiary uppercase">When a message</legend>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="From" value={criteria.from} onChange={(from) => setCriteria((c) => ({ ...c, from }))} autoFocus />
                <Field label="To" value={criteria.to} onChange={(to) => setCriteria((c) => ({ ...c, to }))} />
              </div>
              <Field label="Subject contains" value={criteria.subject} onChange={(subject) => setCriteria((c) => ({ ...c, subject }))} />
              <Field label="Has the words" value={criteria.query} onChange={(query) => setCriteria((c) => ({ ...c, query }))} />
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={criteria.hasAttachment} onChange={(e) => setCriteria((c) => ({ ...c, hasAttachment: e.target.checked }))} className="size-4 rounded border-card-border text-primary-500" />Has an attachment</label>
            </fieldset>
            <fieldset className="space-y-2">
              <legend className="mb-1 text-xs font-semibold tracking-wide text-text-tertiary uppercase">Then</legend>
              {ACTIONS.map((action) => (
                <label key={action.key} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={checked.has(action.key)} className="size-4 rounded border-card-border text-primary-500"
                    onChange={(e) => setChecked((s) => { const n = new Set(s); if (e.target.checked) n.add(action.key); else n.delete(action.key); return n; })} />
                  {action.label}
                </label>
              ))}
              <div className="grid gap-3 pt-2 sm:grid-cols-2">
                <SelectField label="Apply the label" value={label} onChange={(e) => setLabel(e.target.value)} options={[{ value: "", label: "Choose label…" }, ...labels.map((l) => ({ value: l.label_id, label: l.name }))]} />
                <Field label="Forward to" type="email" value={forward} onChange={setForward} hint="Must be a verified forwarding address in Gmail." />
              </div>
            </fieldset>
          </>
        )}
        {error && <p role="alert" className="text-sm text-error-500">{error}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <Button appearance="outline" onPress={onClose}>Cancel</Button>
          <Button type="submit" variant={block ? "danger" : "primary"} isPending={busy}>{block ? "Block sender" : "Create filter"}</Button>
        </div>
      </Form>
    </Dialog>
  );
}
