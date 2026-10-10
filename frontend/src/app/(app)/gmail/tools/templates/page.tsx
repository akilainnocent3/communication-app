"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { usePageTitle } from "@/components/shell/trail";
import { Button } from "@/components/tailgrids/core/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Field } from "@/components/ui/field";
import { SelectField } from "@/components/ui/form";
import { PlusIcon, TemplateIcon, TrashIcon } from "@/components/ui/icons";
import { Page, PageHeader } from "@/components/ui/page";
import { RequestState, TableSkeleton } from "@/components/ui/request-state";
import { SectionCard } from "@/components/ui/section-card";
import { listTime } from "@/lib/format";
import { errorMessage, fieldError, mutate } from "@/services/api/client";
import type { Template } from "@/services/api/types";
import { mailKeys } from "@/platforms/gmail/api/keys";
import { useMailboxSummaries, useTemplates } from "@/platforms/gmail/api/queries";
import { RichTextField } from "@/platforms/gmail/compose/rich-text-field";
import { cn } from "@/utils/cn";

const VARIABLES = ["{{first_name}}", "{{name}}", "{{email}}", "{{my_name}}"];

export default function TemplatesPage() {
  usePageTitle({ page: "Templates", section: "Tools" });
  const templates = useTemplates();
  const [selected, setSelected] = useState<Template | "new" | null>(null);
  const items = templates.data ?? [];
  const current = selected === "new" ? null : selected ?? null;

  return (
    <Page wide>
      <PageHeader title="Templates" description="Reusable replies. Insert one from the compose window; variables are filled in for the first recipient."
        actions={<Button onPress={() => setSelected("new")}><PlusIcon size={16} />New template</Button>} />
      {templates.isPending ? <TableSkeleton rows={4} columns={2} /> : templates.error ? (
        <RequestState loading={false} error={errorMessage(templates.error)} onRetry={() => templates.refetch()} />
      ) : items.length === 0 && !selected ? (
        <SectionCard><EmptyState icon={<TemplateIcon />} title="No templates yet" body="Save answers you send often, like opening hours or payment details." action={<Button onPress={() => setSelected("new")}><PlusIcon size={16} />Create a template</Button>} /></SectionCard>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,320px)_minmax(0,1fr)]">
          <ul className={cn("divide-y divide-card-border self-start overflow-hidden rounded-xl border border-card-border bg-card-surface-area", selected && "hidden lg:block")}>
            {items.map((template) => (
              <li key={template.id}>
                <button type="button" onClick={() => setSelected(template)} aria-current={current?.id === template.id || undefined}
                  className={cn("block w-full px-4 py-3 text-left hover:bg-background-gray-secondary_alt/40 focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none focus-visible:ring-inset",
                    current?.id === template.id && "bg-primary-500/8")}>
                  <span className="block truncate text-sm font-medium text-text-primary">{template.name}</span>
                  <span className="block truncate text-xs text-text-tertiary">{template.subject || "No subject"} · {listTime(template.updated_at)}</span>
                </button>
              </li>
            ))}
          </ul>
          {selected ? <Editor key={current?.id ?? "new"} template={current} onDone={(next) => setSelected(next)} />
            : <SectionCard className="hidden lg:block"><EmptyState compact icon={<TemplateIcon />} title="Choose a template" body="Pick one on the left to edit it." /></SectionCard>}
        </div>
      )}
    </Page>
  );
}

function Editor({ template, onDone }: { template: Template | null; onDone: (next: Template | null) => void }) {
  const client = useQueryClient();
  const boxes = useMailboxSummaries().filter((box) => box.permissions.send);
  const [name, setName] = useState(template?.name ?? "");
  const [subject, setSubject] = useState(template?.subject ?? "");
  const [body, setBody] = useState(template?.body_html ?? "");
  const [mailbox, setMailbox] = useState(template?.mailbox ? String(template.mailbox) : "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [confirm, setConfirm] = useState(false);

  const save = async () => {
    setBusy(true); setError(null);
    const payload = { name, subject, body_html: body, mailbox: mailbox ? Number(mailbox) : null };
    try {
      const saved = template ? await mutate<Template>(`mail/templates/${template.id}/`, "PATCH", payload) : await mutate<Template>("mail/templates/", "POST", payload);
      client.invalidateQueries({ queryKey: mailKeys.templates() });
      toast.success("Template saved.");
      onDone(saved);
    } catch (e) { setError(e); } finally { setBusy(false); }
  };

  return (
    <SectionCard title={template ? "Edit template" : "New template"}
      footer={
        <div className="flex flex-wrap items-center justify-between gap-2">
          {template ? <Button variant="danger" appearance="ghost" onPress={() => setConfirm(true)}><TrashIcon size={16} />Delete</Button> : <span />}
          <div className="flex gap-2"><Button appearance="outline" onPress={() => onDone(null)}>Cancel</Button><Button onPress={save} isPending={busy} isDisabled={!name.trim() || !body.trim()}>Save template</Button></div>
        </div>
      }>
      <div className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Name" value={name} onChange={setName} isRequired error={fieldError(error, "name")} placeholder="Opening hours" />
          <SelectField label="Available in" value={mailbox} onChange={(e) => setMailbox(e.target.value)}
            options={[{ value: "", label: "Every mailbox" }, ...boxes.map((box) => ({ value: String(box.id), label: `${box.office.name} · ${box.email}` }))]} />
        </div>
        <Field label="Subject (optional)" value={subject} onChange={setSubject} />
        <RichTextField label="Message" initial={template?.body_html ?? ""} onChange={setBody} placeholder="Hello {{first_name}}," />
        <p className="text-xs text-text-tertiary">Variables: {VARIABLES.map((v) => <code key={v} className="mr-1.5 rounded bg-background-gray-secondary_alt px-1 py-0.5">{v}</code>)}</p>
        {!!error && !fieldError(error, "name") && <p role="alert" className="text-sm text-error-500">{errorMessage(error)}</p>}
      </div>
      <ConfirmDialog isOpen={confirm} onOpenChange={setConfirm} title={`Delete “${template?.name}”?`} confirmLabel="Delete template" body="This template is removed for everyone."
        onConfirm={async () => {
          if (!template) return;
          try { await mutate(`mail/templates/${template.id}/`, "DELETE"); client.invalidateQueries({ queryKey: mailKeys.templates() }); toast("Template deleted."); onDone(null); }
          catch (e) { toast.error(errorMessage(e)); throw e; }
        }} />
    </SectionCard>
  );
}
