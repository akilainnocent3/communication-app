"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Form } from "react-aria-components";
import { toast } from "sonner";
import { useSession } from "@/components/shell/session-provider";
import { usePageTitle } from "@/components/shell/trail";
import { Button } from "@/components/tailgrids/core/button";
import { Dialog, DialogHeader, DialogTitle } from "@/components/tailgrids/core/dialog";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Field } from "@/components/ui/field";
import { ColourPicker } from "@/components/ui/form";
import { BuildingIcon, PencilIcon, PlusIcon, TrashIcon } from "@/components/ui/icons";
import { Page, PageHeader } from "@/components/ui/page";
import { RequestState } from "@/components/ui/request-state";
import { SectionCard } from "@/components/ui/section-card";
import { errorMessage, fieldError, mutate, request } from "@/services/api/client";
import type { Office } from "@/services/api/types";

const KEY = ["settings", "offices"] as const;

export default function OfficesPage() {
  usePageTitle({ page: "Offices", section: "Settings" });
  const { can } = useSession();
  const client = useQueryClient();
  const offices = useQuery({ queryKey: KEY, queryFn: () => request<Office[]>("settings/offices/") });
  const [editing, setEditing] = useState<Office | "new" | null>(null);
  const [deleting, setDeleting] = useState<Office | null>(null);
  const canEdit = can("identity.manage_users");

  return (
    <Page>
      <PageHeader title="Offices" description="Branches and departments. Each mailbox and user belongs to an office."
        actions={canEdit && <Button onPress={() => setEditing("new")}><PlusIcon size={16} />New office</Button>} />
      {offices.isPending || offices.error ? <RequestState variant="table" loading={offices.isPending} error={errorMessage(offices.error)} onRetry={() => offices.refetch()} /> : offices.data!.length === 0 ? (
        <SectionCard><EmptyState icon={<BuildingIcon />} title="No offices yet" body="Add your head office and branches, then connect their mailboxes." action={canEdit ? <Button onPress={() => setEditing("new")}><PlusIcon size={16} />Add an office</Button> : undefined} /></SectionCard>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {offices.data!.map((office) => (
            <li key={office.id} className="flex items-center gap-3 rounded-xl border border-card-border bg-card-surface-area p-4">
              <span className="flex size-10 shrink-0 items-center justify-center rounded-lg text-sm font-semibold text-white" style={{ background: office.colour || "#3758f9" }} aria-hidden="true">{office.code.slice(0, 3).toUpperCase()}</span>
              <div className="min-w-0 flex-1"><p className="truncate font-medium text-text-primary">{office.name}</p><p className="text-xs text-text-tertiary">Code {office.code}</p></div>
              {canEdit && <>
                <Button size="sm" appearance="ghost" iconOnly aria-label={`Edit ${office.name}`} onPress={() => setEditing(office)}><PencilIcon size={16} /></Button>
                <Button size="sm" appearance="ghost" iconOnly aria-label={`Delete ${office.name}`} onPress={() => setDeleting(office)}><TrashIcon size={16} /></Button>
              </>}
            </li>
          ))}
        </ul>
      )}
      {editing && <OfficeDialog office={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
      <ConfirmDialog isOpen={!!deleting} onOpenChange={(o) => !o && setDeleting(null)} title={`Delete ${deleting?.name}?`} confirmLabel="Delete office" body="Offices that still have mailboxes cannot be deleted. Users in it keep their accounts."
        onConfirm={async () => {
          if (!deleting) return;
          try { await mutate(`settings/offices/${deleting.id}/`, "DELETE"); client.invalidateQueries({ queryKey: KEY }); toast("Office deleted."); }
          catch (e) { toast.error(errorMessage(e)); throw e; }
        }} />
    </Page>
  );
}

function OfficeDialog({ office, onClose }: { office: Office | null; onClose: () => void }) {
  const client = useQueryClient();
  const [name, setName] = useState(office?.name ?? "");
  const [code, setCode] = useState(office?.code ?? "");
  const [colour, setColour] = useState(office?.colour || "#3758f9");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const submit = async () => {
    setBusy(true); setError(null);
    try {
      if (office) await mutate(`settings/offices/${office.id}/`, "PATCH", { name, code, colour }); else await mutate("settings/offices/", "POST", { name, code, colour });
      client.invalidateQueries({ queryKey: KEY }); toast.success("Office saved."); onClose();
    } catch (e) { setError(e); } finally { setBusy(false); }
  };
  return (
    <Dialog isOpen onOpenChange={(o) => !o && onClose()} className="max-w-md">
      <DialogHeader><DialogTitle>{office ? "Edit office" : "New office"}</DialogTitle></DialogHeader>
      <Form className="mt-4 space-y-4" onSubmit={(e) => { e.preventDefault(); submit(); }}>
        <Field label="Name" value={name} onChange={setName} isRequired autoFocus error={fieldError(error, "name")} placeholder="Arusha branch" />
        <Field label="Short code" value={code} onChange={setCode} isRequired error={fieldError(error, "code")} placeholder="ARU" />
        <ColourPicker label="Colour" value={colour} onChange={setColour} />
        {!!error && !fieldError(error, "name") && !fieldError(error, "code") && <p role="alert" className="text-sm text-error-500">{errorMessage(error)}</p>}
        <div className="flex justify-end gap-2 pt-2"><Button appearance="outline" onPress={onClose}>Cancel</Button><Button type="submit" isPending={busy}>Save</Button></div>
      </Form>
    </Dialog>
  );
}
