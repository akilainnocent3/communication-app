"use client";

import { toast } from "sonner";
import { errorMessage, mutate } from "@/services/api/client";
import type { Queued } from "@/services/api/types";
import { dateTime } from "@/lib/format";
import { openCompose, type ComposeInit } from "./store";

type Restored = { mailbox: number; to: ComposeInit["to"]; cc: ComposeInit["cc"]; bcc: ComposeInit["bcc"]; subject: string; html: string; mode: ComposeInit["mode"]; in_reply_to_message: number | null; attachment_ids: number[]; draft_id: number | null; send_as?: string };

/** Cancels a pending send (undo or scheduled) and reopens it in a compose window. */
export async function cancelSend(id: number) {
  const data = await mutate<Restored>(`mail/send/${id}/cancel/`, "POST");
  openCompose({
    mailbox: data.mailbox, to: data.to, cc: data.cc, bcc: data.bcc, subject: data.subject, html: data.html, mode: data.mode ?? "new",
    inReplyToMessage: data.in_reply_to_message ?? undefined, attachmentIds: data.attachment_ids, draftId: data.draft_id ?? undefined, sendAs: data.send_as,
  });
}

async function cancel(queued: Queued, toastId: string | number) {
  try {
    await cancelSend(queued.id);
    toast.dismiss(toastId);
    toast("Sending undone. Your message is back in the editor.");
  } catch (error) {
    toast.error(errorMessage(error));
  }
}

/** "Sending… Undo (8)" countdown for the undo-send window, then "Message sent". Scheduled sends get their own toast. */
export function showSendToast(queued: Queued, onSent?: () => void) {
  if (queued.kind === "scheduled") {
    const id = toast.success(`Send scheduled for ${dateTime(queued.send_at)}.`, { action: { label: "Undo", onClick: () => cancel(queued, id) }, duration: 8000 });
    return;
  }
  const until = new Date(queued.send_at).getTime();
  const seconds = () => Math.max(0, Math.ceil((until - Date.now()) / 1000));
  if (seconds() <= 0) { toast.success("Message sent."); onSent?.(); return; }
  const id = toast.loading(`Sending… ${seconds()}`, { action: { label: "Undo", onClick: () => cancel(queued, id) }, duration: Infinity });
  const timer = window.setInterval(() => {
    const left = seconds();
    if (left <= 0) {
      window.clearInterval(timer);
      toast.success("Message sent.", { id, action: undefined, duration: 4000 });
      onSent?.();
    } else {
      toast.loading(`Sending… ${left}`, { id, action: { label: "Undo", onClick: () => { window.clearInterval(timer); cancel(queued, id); } }, duration: Infinity });
    }
  }, 500);
}
