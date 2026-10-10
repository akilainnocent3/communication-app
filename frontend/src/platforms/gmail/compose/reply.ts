import DOMPurify from "dompurify";
import { fullDate } from "@/lib/format";
import type { Address, Message, ThreadDetail } from "@/services/api/types";
import type { ComposeInit, ComposeMode } from "./store";

const escape = (text: string) => text.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);
const name = (a: Address | null | undefined) => (a ? (a.name ? `${escape(a.name)} &lt;${escape(a.email)}&gt;` : escape(a.email)) : "");
const unique = (list: Address[]) => list.filter((a, i) => list.findIndex((b) => b.email.toLowerCase() === a.email.toLowerCase()) === i);

export function prefixed(subject: string, prefix: "Re:" | "Fwd:") {
  const clean = subject || "(no subject)";
  return new RegExp(`^${prefix}`, "i").test(clean) ? clean : `${prefix} ${clean}`;
}

/** Quoted body for replies/forwards. Remote images stay blocked (they are inert in the quote). */
function quoted(message: Message, mode: ComposeMode) {
  const body = DOMPurify.sanitize(message.body_html || "");
  if (mode === "forward") {
    const header = [
      "---------- Forwarded message ---------",
      `From: ${name(message.from_addr)}`,
      `Date: ${escape(fullDate(message.date))}`,
      `Subject: ${escape(message.subject || "")}`,
      `To: ${message.to.map(name).join(", ")}`,
      ...(message.cc.length ? [`Cc: ${message.cc.map(name).join(", ")}`] : []),
    ].join("<br>");
    return `<p></p><p></p><div>${header}</div><br>${body}`;
  }
  return `<p></p><p></p><p>On ${escape(fullDate(message.date))}, ${name(message.from_addr)} wrote:</p><blockquote>${body}</blockquote>`;
}

/** The compose state for Reply / Reply all / Forward on `message` (Gmail's defaults). */
export function replyInit(thread: ThreadDetail, message: Message, mode: Exclude<ComposeMode, "new">): ComposeInit {
  const me = thread.mailbox.email.toLowerCase();
  const notMe = (a: Address) => a.email.toLowerCase() !== me;
  let to: Address[] = [];
  let cc: Address[] = [];
  if (mode !== "forward") {
    if (message.is_outgoing) to = message.to;
    else to = message.reply_to.length ? message.reply_to : message.from_addr ? [message.from_addr] : [];
    if (mode === "reply_all") {
      cc = unique([...message.to, ...message.cc]).filter(notMe).filter((a) => !to.some((t) => t.email.toLowerCase() === a.email.toLowerCase()));
    }
  }
  return {
    mailbox: thread.mailbox.id,
    mode,
    to: unique(to).filter((a) => mode === "reply" || notMe(a) || message.is_outgoing),
    cc,
    subject: prefixed(message.subject || thread.subject || "", mode === "forward" ? "Fwd:" : "Re:"),
    html: quoted(message, mode),
    threadId: thread.id,
    inReplyToMessage: message.id,
    forwardAttachmentIds: mode === "forward" ? message.attachments.map((a) => a.id) : undefined,
    forwardAttachments: mode === "forward" ? message.attachments.map((a) => ({ id: a.id, filename: a.filename, size: a.size })) : undefined,
  };
}

/** Smart default for the inline reply box: Reply all when the last message had several recipients. */
export function defaultReplyMode(message: Message): "reply" | "reply_all" {
  return message.to.length + message.cc.length > 1 ? "reply_all" : "reply";
}
