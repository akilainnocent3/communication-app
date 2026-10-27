"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/tailgrids/core/button";
import { BlockIcon, CloseIcon, NoteIcon, TrashIcon } from "@/components/ui/icons";
import { m } from "@/i18n";
import { dateTime, minutesLabel, shortDate } from "@/lib/format";
import { errorMessage, mutate } from "@/services/api/client";
import type { ConversationDetail, SmsNote } from "@/services/api/types";
import { cn } from "@/utils/cn";
import { useSession } from "@/components/shell/session-provider";
import { useConversationActions } from "../api/actions";
import { smsKeys } from "../api/keys";
import { useAssignees, useConversation, useNotes } from "../api/queries";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="flex items-start justify-between gap-3 py-1.5 text-sm"><dt className="text-text-tertiary">{label}</dt><dd className="text-right text-text-primary">{children}</dd></div>;
}

/** Contact, conversation stats, assignment, open/done and internal notes (never sent to the phone). */
export function DetailsPanel({ conversationId, onClose }: { conversationId: number; onClose?: () => void }) {
  const conversation = useConversation(conversationId);
  const data = conversation.data;
  if (!data) return null;
  return <Panel data={data} onClose={onClose} />;
}

function Panel({ data, onClose }: { data: ConversationDetail; onClose?: () => void }) {
  const { run } = useConversationActions();
  const assignees = useAssignees(data.permissions.send ? data.device.id : undefined);
  const blocked = data.participants.some((p) => p.is_blocked);
  return (
    <aside className="flex h-full min-h-0 flex-col" aria-label="Conversation details" data-details-panel="">
      <div className="flex h-12 shrink-0 items-center justify-between border-b border-card-border px-4">
        <h2 className="text-sm font-semibold text-text-primary">Details</h2>
        {onClose && <button type="button" onClick={onClose} aria-label={m.common.close} className="flex size-8 items-center justify-center rounded-full text-icon-secondary hover:bg-background-gray-secondary_alt"><CloseIcon size={16} /></button>}
      </div>
      <div className="scrollbar-thin min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-4">
        <section>
          <h3 className="mb-1 text-xs font-semibold tracking-wider text-text-tertiary uppercase">{m.sms.details.contact}</h3>
          <ul className="space-y-2">
            {data.participants.map((p) => (
              <li key={p.address} className="rounded-lg border border-card-border px-3 py-2">
                <p className="font-medium text-text-primary">{p.name || p.display}</p>
                {p.name && <p className="text-xs text-text-secondary">{p.display}</p>}
                <p className="mt-0.5 text-xs text-text-tertiary">{p.name ? m.sms.details.savedOnPhone : m.sms.details.notSaved}{p.is_blocked && " · Blocked"}</p>
              </li>
            ))}
          </ul>
          {data.permissions.manage && (
            <Button size="sm" appearance="outline" className="mt-2" onPress={() => run({ action: blocked ? "unblock" : "block", conversation_ids: [data.id] })}>
              <BlockIcon size={14} />{blocked ? m.sms.details.unblock : m.sms.details.block}
            </Button>
          )}
        </section>
        <section>
          <dl className="divide-y divide-card-border">
            <Row label={m.sms.details.firstContact}>{data.stats.first_contact_at ? shortDate(data.stats.first_contact_at) : "—"}</Row>
            <Row label={m.sms.details.inOut}>{data.stats.inbound} / {data.stats.outbound}</Row>
            <Row label={m.sms.details.avgResponse}>{minutesLabel(data.stats.avg_response_minutes)}</Row>
            <Row label="Phone">{data.device.name}</Row>
            {data.sim && <Row label="SIM">{data.sim.label}</Row>}
          </dl>
        </section>
        {data.permissions.send && (
          <section className="space-y-3">
            <label className="block text-sm">
              <span className="mb-1 block text-xs font-semibold tracking-wider text-text-tertiary uppercase">{m.sms.details.assignment}</span>
              <select value={data.assigned_to?.id ?? ""} aria-label={m.sms.details.assignment}
                onChange={(event) => {
                  const value = event.target.value;
                  run(value ? { action: "assign", conversation_ids: [data.id], assignee: Number(value) } : { action: "unassign", conversation_ids: [data.id] }, { undoable: false });
                }}
                className="h-9 w-full rounded-lg border border-card-border bg-input-background px-3 text-sm text-text-primary">
                <option value="">{m.sms.details.unassigned}</option>
                {(assignees.data ?? []).map((user) => <option key={user.id} value={user.id}>{user.display_name}</option>)}
              </select>
            </label>
            <div role="radiogroup" aria-label={m.sms.details.state} className="inline-flex rounded-lg border border-card-border p-0.5">
              {(["open", "done"] as const).map((state) => (
                <button key={state} type="button" role="radio" aria-checked={data.state === state} onClick={() => data.state !== state && run({ action: state === "done" ? "done" : "reopen", conversation_ids: [data.id] })}
                  className={cn("h-8 rounded-md px-3 text-sm font-medium", data.state === state ? "bg-primary-500 text-white" : "text-text-secondary hover:text-text-primary")}>
                  {state === "open" ? m.sms.details.open : m.sms.details.done}
                </button>
              ))}
            </div>
          </section>
        )}
        <Notes conversationId={data.id} />
      </div>
    </aside>
  );
}

function Notes({ conversationId }: { conversationId: number }) {
  const client = useQueryClient();
  const { me } = useSession();
  const notes = useNotes(conversationId);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const add = async () => {
    if (!text.trim()) return;
    setBusy(true);
    try {
      const note = await mutate<SmsNote>(`sms/conversations/${conversationId}/notes/`, "POST", { body: text });
      client.setQueryData<SmsNote[]>(smsKeys.notes(conversationId), (rows) => [...(rows ?? []), note]);
      setText("");
    } catch (error) { toast.error(errorMessage(error)); } finally { setBusy(false); }
  };
  const remove = async (note: SmsNote) => {
    try {
      await mutate(`sms/conversations/${conversationId}/notes/${note.id}/`, "DELETE");
      client.setQueryData<SmsNote[]>(smsKeys.notes(conversationId), (rows) => rows?.filter((row) => row.id !== note.id));
    } catch (error) { toast.error(errorMessage(error)); }
  };
  return (
    <section>
      <h3 className="mb-1 flex items-center gap-1.5 text-xs font-semibold tracking-wider text-text-tertiary uppercase"><NoteIcon size={14} />{m.sms.details.notes}</h3>
      <p className="mb-2 text-xs text-text-tertiary">{m.sms.details.notesHint}</p>
      <ul className="space-y-2">
        {(notes.data ?? []).map((note) => (
          <li key={note.id} className="group rounded-lg bg-warning-500/10 px-3 py-2 text-sm">
            <p className="whitespace-pre-wrap text-text-primary">{note.body}</p>
            <p className="mt-1 flex items-center gap-2 text-[11px] text-text-tertiary">
              {note.author?.display_name} · {dateTime(note.created_at)}
              {note.author?.id === me?.user.id && <button type="button" onClick={() => remove(note)} aria-label="Delete note" className="ml-auto opacity-0 group-hover:opacity-100 focus-visible:opacity-100"><TrashIcon size={12} /></button>}
            </p>
          </li>
        ))}
      </ul>
      <label htmlFor={`note-${conversationId}`} className="sr-only">{m.sms.details.addNote}</label>
      <textarea id={`note-${conversationId}`} value={text} onChange={(event) => setText(event.target.value)} rows={2} placeholder={m.sms.details.addNote}
        className="mt-2 w-full rounded-lg border border-card-border bg-input-background px-3 py-2 text-sm text-text-primary outline-none focus:border-primary-500" />
      <div className="mt-1.5 flex justify-end"><Button size="sm" onPress={add} isPending={busy} isDisabled={!text.trim()}>{m.sms.details.addNote}</Button></div>
    </section>
  );
}
