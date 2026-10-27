"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { useSession } from "@/components/shell/session-provider";
import { usePageTitle } from "@/components/shell/trail";
import { Button } from "@/components/tailgrids/core/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Field } from "@/components/ui/field";
import { TextAreaField } from "@/components/ui/form";
import { PlusIcon, TemplateIcon, TrashIcon } from "@/components/ui/icons";
import { Page, PageHeader } from "@/components/ui/page";
import { RequestState } from "@/components/ui/request-state";
import { SectionCard, cardClass } from "@/components/ui/section-card";
import { errorMessage, mutate } from "@/services/api/client";
import type { QuickReply } from "@/services/api/types";
import { smsKeys } from "../../api/keys";
import { useDeviceScope, useQuickReplies } from "../../api/queries";
import { segmentInfo } from "../../lib/segments";

/** Reply templates. They appear in the admin composer and are synced to the phones' quick replies. */
export function QuickRepliesPage() {
  usePageTitle({ page: "Quick replies", section: "Tools" });
  const { can } = useSession();
  const [scope] = useDeviceScope();
  const replies = useQuickReplies(scope);
  const client = useQueryClient();
  const [editing, setEditing] = useState<Partial<QuickReply> | null>(null);
  const [remove, setRemove] = useState<QuickReply | null>(null);
  const canEdit = can("sms.manage_devices");
  const save = async () => {
    if (!editing) return;
    try {
      if (editing.id) await mutate(`sms/quick-replies/${editing.id}/`, "PATCH", { title: editing.title, body: editing.body });
      else await mutate("sms/quick-replies/", "POST", { title: editing.title, body: editing.body });
      client.invalidateQueries({ queryKey: ["sms", "quick-replies"] });
      setEditing(null);
      toast.success("Quick reply saved.");
    } catch (error) { toast.error(errorMessage(error)); }
  };
  const info = segmentInfo(editing?.body ?? "");
  return (
    <Page>
      <PageHeader title="Quick replies" description="Ready-made answers for the composer. Phones receive them too, so staff can use them on the phone."
        actions={canEdit && <Button onPress={() => setEditing({ title: "", body: "" })}><PlusIcon size={16} />New quick reply</Button>} />
      {editing && (
        <SectionCard className="mb-4" title={editing.id ? "Edit quick reply" : "New quick reply"}
          footer={<div className="flex justify-end gap-2"><Button appearance="outline" onPress={() => setEditing(null)}>Cancel</Button><Button onPress={save} isDisabled={!editing.title?.trim() || !editing.body?.trim()}>Save</Button></div>}>
          <div className="grid gap-4">
            <Field label="Title" value={editing.title ?? ""} onChange={(title) => setEditing({ ...editing, title })} maxLength={80} autoFocus />
            <TextAreaField label="Text" value={editing.body ?? ""} onChange={(event) => setEditing({ ...editing, body: event.target.value })} maxLength={1000}
              hint={`${info.segments} SMS · ${info.encoding === "ucs2" ? "Unicode" : "GSM-7"}`} />
          </div>
        </SectionCard>
      )}
      {replies.isPending || replies.error ? <RequestState loading={replies.isPending} error={errorMessage(replies.error)} onRetry={() => replies.refetch()} /> : replies.data!.length === 0 ? (
        <div className={cardClass()}><EmptyState icon={<TemplateIcon />} title="No quick replies yet" body="Save the answers you send most often." /></div>
      ) : (
        <ul className="grid gap-3 md:grid-cols-2">
          {replies.data!.map((reply) => (
            <li key={reply.id} className={cardClass({ interactive: canEdit })}>
              <div className="flex items-start gap-2">
                <h2 className="min-w-0 flex-1 truncate font-semibold text-text-primary">{reply.title}</h2>
                {canEdit && <><Button size="sm" appearance="ghost" onPress={() => setEditing(reply)}>Edit</Button>
                  <Button size="sm" appearance="ghost" iconOnly aria-label={`Delete ${reply.title}`} onPress={() => setRemove(reply)}><TrashIcon size={16} /></Button></>}
              </div>
              <p className="mt-1 text-sm whitespace-pre-wrap text-text-secondary">{reply.body}</p>
            </li>
          ))}
        </ul>
      )}
      <ConfirmDialog isOpen={!!remove} onOpenChange={(open) => !open && setRemove(null)} title="Delete quick reply?" confirmLabel="Delete" body={`“${remove?.title}” will be removed from the admin and the phones.`}
        onConfirm={async () => { try { await mutate(`sms/quick-replies/${remove!.id}/`, "DELETE"); client.invalidateQueries({ queryKey: smsKeys.quickReplies(scope) }); client.invalidateQueries({ queryKey: ["sms", "quick-replies"] }); } catch (e) { toast.error(errorMessage(e)); throw e; } }} />
    </Page>
  );
}
