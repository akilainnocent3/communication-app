"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/tailgrids/core/button";
import { AssignIcon, LockIcon, NoteIcon, TrashIcon } from "@/components/ui/icons";
import { ago, initials } from "@/lib/format";
import { errorMessage, mutate } from "@/services/api/client";
import type { Note, ThreadDetail } from "@/services/api/types";
import { useSession } from "@/components/shell/session-provider";
import { useAssignees, useNotes } from "../../api/queries";
import { mailKeys } from "../../api/keys";
import { useThreadActions } from "../../api/actions";

/** Internal notes and assignment for a thread: visible to staff only, never sent to the correspondent. */
export function InternalPanel({ thread }: { thread: ThreadDetail }) {
  const client = useQueryClient();
  const { me } = useSession();
  const notes = useNotes(thread.id);
  const assignees = useAssignees(thread.mailbox.id);
  const actions = useThreadActions();
  const [body, setBody] = useState("");
  const assignment = thread.assignment as { assignee?: { id?: number; display_name?: string }; status?: string } | null;
  const canOrganise = thread.permissions.send;

  const add = useMutation({
    mutationFn: (text: string) => mutate<Note>(`mail/threads/${thread.id}/notes/`, "POST", { body: text }),
    onSuccess: (note) => { client.setQueryData<Note[]>(mailKeys.notes(thread.id), (list) => [...(list ?? []), note]); setBody(""); },
    onError: (error) => toast.error(errorMessage(error)),
  });
  const remove = useMutation({
    mutationFn: (id: number) => mutate(`mail/threads/${thread.id}/notes/${id}/`, "DELETE"),
    onMutate: (id) => client.setQueryData<Note[]>(mailKeys.notes(thread.id), (list) => (list ?? []).filter((note) => note.id !== id)),
    onError: (error) => { toast.error(errorMessage(error)); client.invalidateQueries({ queryKey: mailKeys.notes(thread.id) }); },
  });

  return (
    <section aria-labelledby={`internal-${thread.id}`} className="mx-4 mb-4 rounded-xl border border-dashed border-warning-500/50 bg-warning-500/[0.04] p-4 sm:mx-6">
      <h2 id={`internal-${thread.id}`} className="flex items-center gap-2 text-sm font-semibold text-text-primary">
        <LockIcon size={16} className="text-warning-500" /> Internal
        <span className="rounded-full bg-warning-500/15 px-2 py-0.5 text-[11px] font-medium text-badge-warning-text">Not sent · staff only</span>
      </h2>

      <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
        <AssignIcon size={16} className="text-icon-tertiary" />
        <label htmlFor={`assign-${thread.id}`} className="text-text-secondary">Assigned to</label>
        <select
          id={`assign-${thread.id}`}
          disabled={!canOrganise || actions.isPending}
          value={assignment?.assignee?.id ?? ""}
          onChange={(event) => {
            const value = event.target.value;
            actions.run(value ? { action: "assign", thread_ids: [thread.id], assignee: Number(value) } : { action: "unassign", thread_ids: [thread.id] });
          }}
          className="h-9 min-w-44 rounded-lg border border-card-border bg-card-surface-area pr-8 pl-2.5 text-sm text-text-primary focus:border-primary-500 focus:ring-2 focus:ring-primary-500/30 disabled:opacity-60"
        >
          <option value="">Nobody</option>
          {(assignees.data ?? []).map((user) => <option key={user.id} value={user.id}>{user.display_name}{user.id === me?.user.id ? " (me)" : ""}</option>)}
        </select>
        {assignment?.assignee && me && assignment.assignee.id !== me.user.id && canOrganise && (
          <button type="button" className="text-xs font-medium text-primary-600 hover:underline dark:text-primary-300" onClick={() => actions.run({ action: "assign", thread_ids: [thread.id], assignee: me.user.id })}>Assign to me</button>
        )}
      </div>

      <ul className="mt-4 space-y-3" aria-live="polite">
        {(notes.data ?? []).map((note) => {
          const author = note.author as { id?: number; display_name?: string };
          return (
            <li key={note.id} className="flex gap-2.5">
              <span aria-hidden="true" className="flex size-7 shrink-0 items-center justify-center rounded-full bg-warning-500/20 text-[11px] font-semibold text-badge-warning-text">{initials(author.display_name ?? "?")}</span>
              <div className="min-w-0 flex-1 rounded-lg bg-card-surface-area px-3 py-2 shadow-xs">
                <p className="flex items-center gap-2 text-xs"><span className="font-semibold text-text-primary">{author.display_name}</span><span className="text-text-tertiary">{ago(note.created_at)}</span>
                  {author.id === me?.user.id && (
                    <button type="button" onClick={() => remove.mutate(note.id)} aria-label="Delete note" className="ml-auto text-icon-tertiary hover:text-error-500"><TrashIcon size={14} /></button>
                  )}
                </p>
                <p className="mt-0.5 text-sm whitespace-pre-wrap text-text-primary">{note.body}</p>
              </div>
            </li>
          );
        })}
      </ul>

      <form className="mt-3 flex items-start gap-2" onSubmit={(event) => { event.preventDefault(); if (body.trim()) add.mutate(body.trim()); }}>
        <label htmlFor={`note-${thread.id}`} className="sr-only">Add an internal note</label>
        <textarea id={`note-${thread.id}`} rows={1} value={body} onChange={(event) => setBody(event.target.value)} placeholder="Add an internal note (colleagues only)…"
          onKeyDown={(event) => { if (event.key === "Enter" && (event.metaKey || event.ctrlKey) && body.trim()) add.mutate(body.trim()); }}
          className="min-h-10 flex-1 resize-y rounded-lg border border-card-border bg-card-surface-area px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-primary-500 focus:ring-2 focus:ring-primary-500/30 focus:outline-none" />
        <Button type="submit" appearance="outline" isPending={add.isPending} isDisabled={!body.trim()}><NoteIcon size={16} />Add note</Button>
      </form>
    </section>
  );
}
