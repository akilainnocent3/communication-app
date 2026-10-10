"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Dialog as AriaDialog, Popover } from "react-aria-components";
import { toast } from "sonner";
import { Button } from "@/components/tailgrids/core/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/tailgrids/core/dropdown";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { AttachmentIcon, ChevronDownIcon, CloseIcon, ExternalIcon, FileIcon, TemplateIcon, TrashIcon } from "@/components/ui/icons";
import { useSession } from "@/components/shell/session-provider";
import { bytes } from "@/lib/format";
import { errorMessage, mutate, upload } from "@/services/api/client";
import type { Address, ComposeRequest, Draft, Queued, Template, Uploaded } from "@/services/api/types";
import { cn } from "@/utils/cn";
import { mailKeys } from "../api/keys";
import { useMailboxSummaries, useSendAs, useTemplates } from "../api/queries";
import { TimePicker, snoozePresets } from "../components/mail/snooze-picker";
import { ComposeEditorContent, EditorToolbar, useComposeEditor } from "./editor";
import { RecipientInput } from "./recipient-input";
import { showSendToast } from "./send-toast";
import type { ComposeInit, ComposeMode } from "./store";

const MAX_TOTAL = 25 * 1024 * 1024;
const MENTIONS_ATTACHMENT = /\b(attach(ed|ment|ments|ing)?|enclosed|see the file|kiambatisho|nimeambatisha|imeambatishwa)\b/i;

type LocalAttachment = { key: string; name: string; size: number; progress: number; id?: number; error?: string; forwarded?: boolean; fid?: string };

export type ComposeState = ComposeInit;

/** Template variables: {{first_name}}, {{name}}, {{email}}, {{my_name}}. */
function fillTemplate(text: string, to: Address | undefined, myName: string) {
  const name = to?.name || to?.email.split("@")[0] || "";
  return text
    .replaceAll("{{first_name}}", name.split(/\s+/)[0] ?? "")
    .replaceAll("{{name}}", name)
    .replaceAll("{{email}}", to?.email ?? "")
    .replaceAll("{{my_name}}", myName);
}

/** Text the user actually typed (excluding the quoted reply), for the "missing attachment?" check. */
function ownText(html: string) {
  const cut = html.split(/<blockquote|---------- Forwarded message/i)[0];
  return cut.replace(/<[^>]+>/g, " ");
}

export function useComposeForm(init: ComposeInit, onClosed: () => void) {
  const client = useQueryClient();
  const { me, preferences } = useSession();
  const mailboxes = useMailboxSummaries().filter((box) => box.permissions.send);
  const [mailbox, setMailbox] = useState<number | undefined>(init.mailbox && mailboxes.some((b) => b.id === init.mailbox) ? init.mailbox : mailboxes[0]?.id);
  const sendAsList = useSendAs(mailbox);
  const [sendAs, setSendAs] = useState(init.sendAs ?? "");
  const [to, setTo] = useState<Address[]>(init.to ?? []);
  const [cc, setCc] = useState<Address[]>(init.cc ?? []);
  const [bcc, setBcc] = useState<Address[]>(init.bcc ?? []);
  const [showCc, setShowCc] = useState(!!init.cc?.length);
  const [showBcc, setShowBcc] = useState(!!init.bcc?.length);
  const [subject, setSubject] = useState(init.subject ?? "");
  const [attachments, setAttachments] = useState<LocalAttachment[]>(() => [
    ...(init.attachmentIds ?? []).map((id) => ({ key: `u${id}`, id, name: "Attachment", size: 0, progress: 1 })),
    ...(init.forwardAttachmentIds ?? []).map((fid) => {
      const meta = init.forwardAttachments?.find((item) => item.id === fid);
      return { key: `f${fid}`, name: meta?.filename ?? "Forwarded attachment", size: meta?.size ?? 0, progress: 1, forwarded: true, fid };
    }),
  ]);
  const [draftId, setDraftId] = useState<number | undefined>(init.draftId);
  const [saveState, setSaveState] = useState<"idle" | "dirty" | "saving" | "saved" | "error">("idle");
  const [sending, setSending] = useState(false);
  const html = useRef(init.html ?? "");
  const text = useRef("");
  const mode: ComposeMode = init.mode ?? "new";

  // Signature: inserted once for new messages and replies (above the quote), from the chosen alias.
  const signatureDone = useRef(!!init.draftId);
  const alias = (sendAsList.data ?? []).find((item) => item.email === sendAs) ?? (sendAsList.data ?? []).find((item) => item.is_default) ?? sendAsList.data?.[0];

  const markDirty = useCallback(() => setSaveState("dirty"), []);
  const editor = useComposeEditor({
    initial: init.html ?? "",
    placeholder: mode === "new" ? "Write your message…" : "Write your reply…",
    onChange: (value, plain) => { html.current = value; text.current = plain; markDirty(); },
    onPasteFiles: (files) => addFiles(files),
  });

  useEffect(() => {
    if (signatureDone.current || !editor || !alias || sendAsList.isPending) return;
    signatureDone.current = true;
    if (!alias.signature) return;
    const signature = `<p></p><p>-- </p>${alias.signature}`;
    if (mode === "new") editor.commands.setContent(`<p></p>${signature}`, { emitUpdate: false });
    else editor.commands.setContent(`<p></p>${signature}${html.current}`, { emitUpdate: false });
    html.current = editor.getHTML();
    editor.commands.focus("start");
  }, [editor, alias, sendAsList.isPending, mode]);

  const uploadIds = attachments.filter((a) => a.id && !a.forwarded).map((a) => a.id!) as number[];
  const forwardIds = attachments.filter((a) => a.forwarded && a.fid).map((a) => a.fid!);
  const totalSize = attachments.reduce((sum, a) => sum + a.size, 0);

  const payload = useCallback((): Omit<ComposeRequest, "mailbox"> & { mailbox: number } => ({
    mailbox: mailbox!,
    send_as: sendAs || undefined,
    to, cc, bcc,
    subject,
    html: html.current,
    mode,
    in_reply_to_message: init.inReplyToMessage ?? null,
    attachment_ids: uploadIds,
    forward_attachment_ids: forwardIds,
    draft_id: draftId ?? null,
  }), [mailbox, sendAs, to, cc, bcc, subject, mode, init.inReplyToMessage, uploadIds, forwardIds, draftId]);

  const saveDraft = useCallback(async () => {
    if (!mailbox) return;
    setSaveState("saving");
    try {
      const body = payload();
      const draft = draftId
        ? await mutate<Draft>(`mail/drafts/${draftId}/`, "PATCH", body)
        : await mutate<Draft>("mail/drafts/", "POST", body);
      setDraftId(draft.id);
      setSaveState("saved");
      client.invalidateQueries({ queryKey: mailKeys.drafts() });
    } catch {
      setSaveState("error");
    }
  }, [mailbox, payload, draftId, client]);

  // Autosave 2 s after the last change.
  const fields = JSON.stringify([to, cc, bcc, subject, sendAs, mailbox, uploadIds]);
  const firstFields = useRef(fields);
  useEffect(() => { if (fields !== firstFields.current) markDirty(); }, [fields, markDirty]);
  useEffect(() => {
    if (saveState !== "dirty") return;
    const timer = window.setTimeout(saveDraft, 2000);
    return () => window.clearTimeout(timer);
  }, [saveState, saveDraft, fields]);

  useEffect(() => {
    if (saveState !== "dirty" && saveState !== "saving") return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [saveState]);

  function addFiles(files: File[]) {
    if (!mailbox) return;
    let running = totalSize;
    for (const file of files) {
      if (running + file.size > MAX_TOTAL) { toast.error(`${file.name} would make the message larger than 25 MB. Share it with a link instead.`); continue; }
      running += file.size;
      const key = `${Date.now()}-${file.name}-${Math.random()}`;
      setAttachments((list) => [...list, { key, name: file.name, size: file.size, progress: 0 }]);
      const form = new FormData();
      form.append("file", file);
      form.append("mailbox", String(mailbox));
      upload<Uploaded>("mail/uploads/", form, (fraction) => setAttachments((list) => list.map((a) => (a.key === key ? { ...a, progress: fraction } : a))))
        .then((result) => setAttachments((list) => list.map((a) => (a.key === key ? { ...a, id: result.id, progress: 1 } : a))))
        .catch((error) => setAttachments((list) => list.map((a) => (a.key === key ? { ...a, error: errorMessage(error) } : a))));
    }
  }
  const removeAttachment = (key: string) => {
    const item = attachments.find((a) => a.key === key);
    setAttachments((list) => list.filter((a) => a.key !== key));
    if (item?.id && !item.forwarded) mutate(`mail/uploads/${item.id}/`, "DELETE").catch(() => undefined);
  };

  const insertTemplate = (template: Template) => {
    const filled = fillTemplate(template.body_html, to[0], me?.user.display_name ?? "");
    if (!subject.trim() && template.subject) setSubject(fillTemplate(template.subject, to[0], me?.user.display_name ?? ""));
    editor?.chain().focus().insertContent(filled).run();
  };

  const uploading = attachments.some((a) => a.progress < 1 && !a.error);
  const send = async (sendAt?: Date) => {
    if (!mailbox) return;
    setSending(true);
    try {
      const queued = await mutate<Queued>("mail/send/", "POST", {
        ...payload(),
        send_at: sendAt ? sendAt.toISOString() : null,
        undo_seconds: sendAt ? null : preferences.undo_send_seconds,
      });
      onClosed();
      client.invalidateQueries({ queryKey: mailKeys.drafts() });
      client.invalidateQueries({ queryKey: mailKeys.scheduled() });
      showSendToast(queued, () => {
        client.invalidateQueries({ queryKey: mailKeys.threadLists() });
        if (init.threadId) client.invalidateQueries({ queryKey: mailKeys.thread(init.threadId) });
      });
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setSending(false);
    }
  };

  const discard = async () => {
    onClosed();
    if (draftId) {
      try { await mutate(`mail/drafts/${draftId}/`, "DELETE"); client.invalidateQueries({ queryKey: mailKeys.drafts() }); toast("Draft discarded."); }
      catch (error) { toast.error(errorMessage(error)); }
    }
  };

  /** Closing keeps the draft (saved now if there are unsaved changes), like Gmail. */
  const close = async () => {
    const hasContent = to.length || subject.trim() || text.current.trim() || attachments.length;
    if (saveState === "dirty" && hasContent) { await saveDraft(); toast("Draft saved."); }
    onClosed();
  };

  return {
    mailboxes, mailbox, setMailbox, sendAsList: sendAsList.data ?? [], sendAs: sendAs || alias?.email || "", setSendAs,
    to, setTo, cc, setCc, bcc, setBcc, showCc, setShowCc, showBcc, setShowBcc, subject, setSubject,
    attachments, addFiles, removeAttachment, totalSize, uploading, insertTemplate,
    editor, saveState, sending, send, discard, close, mode, html, text, payload, draftId,
  };
}

export type ComposeController = ReturnType<typeof useComposeForm>;

function SaveIndicator({ state }: { state: ComposeController["saveState"] }) {
  const label = { idle: "", dirty: "", saving: "Saving…", saved: "Saved", error: "Couldn't save draft" }[state];
  if (!label) return null;
  return <span role="status" aria-live="polite" className={cn("text-xs", state === "error" ? "text-error-500" : "text-text-tertiary")}>{label}</span>;
}

/** The body of a compose window / inline reply: From, recipients, subject, editor, attachments and the send bar. */
export function ComposeFields({ c, variant, onPopOut }: { c: ComposeController; variant: "window" | "inline"; onPopOut?: () => void }) {
  const templates = useTemplates();
  const fileInput = useRef<HTMLInputElement>(null);
  const scheduleRef = useRef<HTMLButtonElement>(null);
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [warning, setWarning] = useState<null | { title: string; body: string; sendAt?: Date }>(null);
  const presets = useMemo(() => snoozePresets().map((p) => ({ ...p, label: p.label === "Later today" ? "This evening" : p.label })), []);

  const trySend = (sendAt?: Date) => {
    if (!c.to.length && !c.cc.length && !c.bcc.length) { toast.error("Add at least one recipient."); return; }
    if (c.uploading) { toast("Wait for the attachments to finish uploading."); return; }
    if (MENTIONS_ATTACHMENT.test(ownText(c.html.current)) && !c.attachments.length) {
      setWarning({ title: "Missing attachment?", body: "You wrote about an attachment, but nothing is attached. Send anyway?", sendAt }); return;
    }
    if (!c.subject.trim()) { setWarning({ title: "Send without a subject?", body: "This message has no subject.", sendAt }); return; }
    c.send(sendAt);
  };
  const multipleFrom = c.mailboxes.length > 1 || c.sendAsList.length > 1;

  return (
    <div
      className={cn("relative flex min-h-0 flex-1 flex-col", dragging && "ring-2 ring-primary-500 ring-inset")}
      onDragOver={(event) => { if (event.dataTransfer.types.includes("Files")) { event.preventDefault(); setDragging(true); } }}
      onDragLeave={(event) => { if (event.currentTarget === event.target) setDragging(false); }}
      onDrop={(event) => { event.preventDefault(); setDragging(false); c.addFiles(Array.from(event.dataTransfer.files)); }}
      onKeyDown={(event) => { if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) { event.preventDefault(); trySend(); } }}
    >
      <div className={cn("shrink-0", variant === "window" ? "px-4" : "")}>
        {multipleFrom && (
          <div className="flex min-h-10 items-center gap-2 border-b border-card-border">
            <label htmlFor="compose-from" className="w-10 shrink-0 text-sm text-text-tertiary">From</label>
            <select id="compose-from" value={`${c.mailbox}|${c.sendAs}`} onChange={(event) => { const [box, alias] = event.target.value.split("|"); c.setMailbox(Number(box)); c.setSendAs(alias); }}
              className="h-9 min-w-0 flex-1 border-0 bg-transparent py-0 pl-0 text-sm text-text-primary focus:ring-0">
              {c.mailboxes.map((box) => box.id === c.mailbox && c.sendAsList.length
                ? c.sendAsList.map((alias) => <option key={`${box.id}|${alias.email}`} value={`${box.id}|${alias.email}`}>{alias.display_name ? `${alias.display_name} <${alias.email}>` : alias.email}</option>)
                : <option key={box.id} value={`${box.id}|`}>{box.name} &lt;{box.email}&gt;</option>)}
            </select>
          </div>
        )}
        <RecipientInput label="To" value={c.to} onChange={c.setTo} mailbox={c.mailbox} autoFocus={c.mode === "new" || c.mode === "forward"}
          trailing={(
            <span className="flex shrink-0 gap-2 pt-1.5 text-sm text-text-tertiary">
              {!c.showCc && <button type="button" className="hover:text-text-primary hover:underline" onClick={() => c.setShowCc(true)}>Cc</button>}
              {!c.showBcc && <button type="button" className="hover:text-text-primary hover:underline" onClick={() => c.setShowBcc(true)}>Bcc</button>}
            </span>
          )} />
        {c.showCc && <RecipientInput label="Cc" value={c.cc} onChange={c.setCc} mailbox={c.mailbox} />}
        {c.showBcc && <RecipientInput label="Bcc" value={c.bcc} onChange={c.setBcc} mailbox={c.mailbox} />}
        {(variant === "window" || c.mode === "forward") && (
          <input aria-label="Subject" placeholder="Subject" value={c.subject} onChange={(event) => c.setSubject(event.target.value)}
            className="h-10 w-full border-0 border-b border-card-border bg-transparent px-0 text-sm text-text-primary placeholder:text-text-tertiary focus:border-primary-500 focus:ring-0" />
        )}
      </div>

      <div className={cn("scrollbar-thin min-h-24 flex-1 overflow-y-auto", variant === "window" ? "px-4" : "")} onClick={() => c.editor?.commands.focus()}>
        <ComposeEditorContent editor={c.editor} className="h-full" />
        {c.attachments.length > 0 && (
          <ul className="my-2 space-y-1.5">
            {c.attachments.map((item) => (
              <li key={item.key} className="flex items-center gap-2 rounded-lg border border-card-border bg-background-gray-secondary_alt/40 px-2.5 py-1.5 text-xs">
                <FileIcon size={16} className="shrink-0 text-icon-tertiary" />
                <span className="min-w-0 flex-1 truncate font-medium text-text-primary">{item.name}</span>
                {item.size > 0 && <span className="shrink-0 text-text-tertiary">{bytes(item.size)}</span>}
                {item.error ? <span className="shrink-0 text-error-500">{item.error}</span> : item.progress < 1 && (
                  <span className="h-1.5 w-20 shrink-0 overflow-hidden rounded-full bg-background-gray-secondary" role="progressbar" aria-label={`Uploading ${item.name}`} aria-valuenow={Math.round(item.progress * 100)} aria-valuemin={0} aria-valuemax={100}>
                    <span className="block h-full bg-primary-500 transition-[width]" style={{ width: `${Math.round(item.progress * 100)}%` }} />
                  </span>
                )}
                <button type="button" aria-label={`Remove ${item.name}`} onClick={() => c.removeAttachment(item.key)} className="flex size-6 items-center justify-center rounded text-icon-tertiary hover:text-text-primary"><CloseIcon size={14} /></button>
              </li>
            ))}
          </ul>
        )}
        {c.totalSize > MAX_TOTAL * 0.8 && <p className="mb-2 text-xs text-warning-500">Attachments total {bytes(c.totalSize)} of the 25 MB limit.</p>}
      </div>

      <div className={cn("flex shrink-0 flex-wrap items-center gap-1 border-t border-card-border py-2", variant === "window" ? "px-3" : "")}>
        <div className="flex items-center">
          <Button onPress={() => trySend()} isPending={c.sending} className="rounded-r-none pr-4 pl-5" aria-label="Send (Ctrl+Enter)">Send</Button>
          <button ref={scheduleRef} type="button" aria-label="Schedule send" title="Schedule send" onClick={() => setScheduleOpen(true)}
            className="flex h-9 w-8 items-center justify-center rounded-r-lg border-l border-white/30 bg-primary-500 text-white hover:bg-primary-600 focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none">
            <ChevronDownIcon size={16} />
          </button>
        </div>
        <EditorToolbar editor={c.editor} className="ml-1 max-sm:hidden" />
        <span aria-hidden="true" className="mx-0.5 h-5 w-px bg-card-border max-sm:hidden" />
        <input ref={fileInput} type="file" multiple hidden onChange={(event) => { c.addFiles(Array.from(event.target.files ?? [])); event.target.value = ""; }} />
        <button type="button" aria-label="Attach files" title="Attach files" onClick={() => fileInput.current?.click()} className="flex size-8 items-center justify-center rounded-md text-icon-secondary hover:bg-background-gray-secondary_alt hover:text-text-primary"><AttachmentIcon /></button>
        <DropdownMenu>
          <DropdownMenuTrigger aria-label="Insert template" className="flex size-8 items-center justify-center rounded-md text-icon-secondary hover:bg-background-gray-secondary_alt hover:text-text-primary"><TemplateIcon /></DropdownMenuTrigger>
          <DropdownMenuContent placement="top start" className="max-h-72 w-64 overflow-y-auto p-1.5">
            {(templates.data ?? []).filter((t) => !t.mailbox || t.mailbox === c.mailbox).map((template) => (
              <DropdownMenuItem key={template.id} onAction={() => c.insertTemplate(template)} className="flex-col items-start gap-0 px-3 py-2">
                <span className="font-medium text-text-primary">{template.name}</span>
                {template.subject && <span className="truncate text-xs text-text-tertiary">{template.subject}</span>}
              </DropdownMenuItem>
            ))}
            {!templates.data?.length && <DropdownMenuItem href="/gmail/tools/templates" className="px-3 py-2 text-text-tertiary">No templates yet · Create one</DropdownMenuItem>}
          </DropdownMenuContent>
        </DropdownMenu>
        <div className="ml-auto flex items-center gap-1.5">
          <SaveIndicator state={c.saveState} />
          {onPopOut && <button type="button" aria-label="Pop out" title="Pop out" onClick={onPopOut} className="flex size-8 items-center justify-center rounded-md text-icon-secondary hover:bg-background-gray-secondary_alt hover:text-text-primary"><ExternalIcon /></button>}
          <button type="button" aria-label="Discard draft" title="Discard draft" onClick={c.discard} className="flex size-8 items-center justify-center rounded-md text-icon-secondary hover:bg-background-gray-secondary_alt hover:text-error-500"><TrashIcon /></button>
        </div>
      </div>
      <EditorToolbar editor={c.editor} className={cn("border-t border-card-border py-1 sm:hidden", variant === "window" ? "px-3" : "")} />

      <Popover triggerRef={scheduleRef} isOpen={scheduleOpen} onOpenChange={setScheduleOpen} placement="top start"
        className="overflow-hidden rounded-xl border border-card-border bg-card-surface-area shadow-lg outline-none entering:animate-pop-in">
        <AriaDialog aria-label="Schedule send" className="outline-none">
          <TimePicker title="Schedule send" presets={presets} confirm="Schedule send" onClose={() => setScheduleOpen(false)} onPick={(date) => { setScheduleOpen(false); trySend(date); }} />
        </AriaDialog>
      </Popover>
      <ConfirmDialog isOpen={!!warning} onOpenChange={(open) => !open && setWarning(null)} tone="primary" title={warning?.title ?? ""} body={warning?.body}
        confirmLabel="Send anyway" onConfirm={() => c.send(warning?.sendAt)} />
      {dragging && <div aria-hidden="true" className="pointer-events-none absolute inset-0 flex items-center justify-center bg-primary-500/10 text-sm font-semibold text-primary-600">Drop files to attach</div>}
    </div>
  );
}

/** Inline reply box at the bottom of a thread. */
export function InlineReply({ init, onClose, onPopOut, onSent }: { init: ComposeInit; onClose: () => void; onPopOut: (state: ComposeInit) => void; onSent?: () => void }) {
  const c = useComposeForm(init, () => { onClose(); onSent?.(); });
  const label = { reply: "Reply", reply_all: "Reply all", forward: "Forward", new: "New message" }[c.mode];
  return (
    <section aria-label={label} className="animate-fade-up rounded-xl border border-card-border bg-card-surface-area px-4 pt-2 shadow-[0_1px_3px_rgba(0,0,0,0.08)] sm:ml-[52px]">
      <div className="flex items-center justify-between pb-1">
        <p className="text-xs font-semibold tracking-wide text-text-tertiary uppercase">{label}</p>
        <button type="button" aria-label="Close reply" onClick={c.close} className="flex size-8 items-center justify-center rounded-md text-icon-tertiary hover:text-text-primary"><CloseIcon size={16} /></button>
      </div>
      <div className="flex min-h-56 flex-col">
        <ComposeFields c={c} variant="inline" onPopOut={() => onPopOut({ ...init, to: c.to, cc: c.cc, bcc: c.bcc, subject: c.subject, html: c.html.current, mailbox: c.mailbox, draftId: c.draftId })} />
      </div>
    </section>
  );
}
