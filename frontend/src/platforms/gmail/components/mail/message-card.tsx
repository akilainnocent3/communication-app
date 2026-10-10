"use client";

import { useState } from "react";
import { Dialog as AriaDialog, DialogTrigger, Popover, Button as AriaButton } from "react-aria-components";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/tailgrids/core/dropdown";
import { ChevronDownIcon, CodeIcon, DotsVerticalIcon, ForwardIcon, ImageIcon, ReplyAllIcon, ReplyIcon, UnsubscribeIcon, WarningIcon } from "@/components/ui/icons";
import { avatarHue, fullDate, initials, messageTime } from "@/lib/format";
import type { Address, Message } from "@/services/api/types";
import { cn } from "@/utils/cn";
import { Attachments } from "./attachments";
import { EmailFrame } from "./email-frame";
import { displayName } from "./participants";

export function SenderAvatar({ address, size = 40 }: { address: Address | null; size?: number }) {
  const seed = address?.email ?? "?";
  const hue = avatarHue(seed);
  return (
    <span aria-hidden="true" className="flex shrink-0 items-center justify-center rounded-full font-semibold text-white"
      style={{ width: size, height: size, fontSize: size * 0.38, background: `hsl(${hue} 55% 48%)` }}>
      {initials(displayName(address))}
    </span>
  );
}

const list = (addresses: Address[]) => addresses.map((a) => displayName(a)).join(", ");

function Recipients({ message, myEmail }: { message: Message; myEmail?: string }) {
  const to = message.to.map((a) => (a.email.toLowerCase() === myEmail?.toLowerCase() ? "me" : displayName(a)));
  const short = [...to, ...message.cc.map((a) => displayName(a))].join(", ");
  const rows: [string, string][] = [
    ["from", message.from_addr ? `${displayName(message.from_addr)} <${message.from_addr.email}>` : "—"],
    ["to", message.to.map((a) => `${displayName(a)} <${a.email}>`).join(", ") || "—"],
    ...(message.cc.length ? [["cc", message.cc.map((a) => `${displayName(a)} <${a.email}>`).join(", ")] as [string, string]] : []),
    ...(message.bcc.length ? [["bcc", list(message.bcc)] as [string, string]] : []),
    ...(message.reply_to.length ? [["reply-to", list(message.reply_to)] as [string, string]] : []),
    ["date", fullDate(message.date)],
    ["subject", message.subject || "(no subject)"],
  ];
  return (
    <DialogTrigger>
      <AriaButton className="flex max-w-full items-center gap-0.5 rounded text-xs text-text-tertiary hover:text-text-primary focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none" aria-label="Show details">
        <span className="truncate">to {short || "undisclosed recipients"}</span><ChevronDownIcon size={14} className="shrink-0" />
      </AriaButton>
      <Popover placement="bottom start" className="max-w-[min(32rem,calc(100vw-2rem))] rounded-xl border border-card-border bg-card-surface-area p-4 shadow-lg outline-none entering:animate-pop-in">
        <AriaDialog aria-label="Message details" className="outline-none">
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-xs">
            {rows.map(([key, value]) => (<div key={key} className="contents"><dt className="text-right text-text-tertiary">{key}:</dt><dd className="break-words text-text-primary">{value}</dd></div>))}
          </dl>
        </AriaDialog>
      </Popover>
    </DialogTrigger>
  );
}

export type MessageActions = {
  onReply: (message: Message, mode: "reply" | "reply_all" | "forward") => void;
  onShowImages: (message: Message, always: boolean) => void;
  onUnsubscribe: (message: Message) => void;
  onShowOriginal: (message: Message) => void;
};

/** One message in a thread: collapsed (sender + snippet) or expanded (headers, body, attachments). */
export function MessageCard({ message, expanded, onToggle, actions, myEmail, imagesShown, canSend, last }: {
  message: Message; expanded: boolean; onToggle: () => void; actions: MessageActions; myEmail?: string; imagesShown: boolean; canSend: boolean; last: boolean;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const from = message.from_addr;
  const allowed = imagesShown || message.images_shown;
  const many = message.to.length + message.cc.length > 1;
  if (!expanded)
    return (
      <button type="button" onClick={onToggle} aria-expanded={false}
        className="flex w-full items-center gap-3 border-t border-card-border px-4 py-3 text-left transition-colors hover:bg-background-gray-secondary_alt/50 focus-visible:bg-background-gray-secondary_alt/50 focus-visible:outline-none sm:px-6">
        <SenderAvatar address={from} size={32} />
        <span className={cn("w-40 shrink-0 truncate text-sm", message.is_unread ? "font-semibold text-text-primary" : "text-text-primary")}>{displayName(from)}</span>
        <span className="min-w-0 flex-1 truncate text-sm text-text-tertiary">{message.snippet}</span>
        <time className="shrink-0 text-xs text-text-tertiary" dateTime={message.date}>{messageTime(message.date)}</time>
      </button>
    );
  return (
    <article className="border-t border-card-border px-4 pt-4 pb-5 first:border-t-0 sm:px-6" aria-label={`Message from ${displayName(from)}`}>
      <header className="flex items-start gap-3">
        <SenderAvatar address={from} />
        <div className="min-w-0 flex-1">
          <button type="button" onClick={onToggle} aria-expanded className="flex min-w-0 max-w-full flex-wrap items-baseline gap-x-1.5 text-left focus-visible:outline-none" disabled={last}>
            <span className="truncate text-sm font-semibold text-text-primary">{displayName(from)}</span>
            {from?.name && <span className="truncate text-xs text-text-tertiary">&lt;{from.email}&gt;</span>}
          </button>
          <Recipients message={message} myEmail={myEmail} />
        </div>
        <div className="flex shrink-0 items-center gap-0.5">
          <time className="mr-1 hidden text-xs text-text-tertiary sm:inline" dateTime={message.date} title={fullDate(message.date)}>{messageTime(message.date)}</time>
          {canSend && (
            <button type="button" aria-label="Reply" title="Reply" onClick={() => actions.onReply(message, "reply")}
              className="flex size-9 items-center justify-center rounded-full text-icon-secondary hover:bg-background-gray-secondary_alt hover:text-text-primary focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none"><ReplyIcon /></button>
          )}
          <DropdownMenu isOpen={menuOpen} onOpenChange={setMenuOpen}>
            <DropdownMenuTrigger aria-label="More message actions" className="flex size-9 items-center justify-center rounded-full text-icon-secondary hover:bg-background-gray-secondary_alt hover:text-text-primary focus-visible:ring-2 focus-visible:ring-primary-500"><DotsVerticalIcon /></DropdownMenuTrigger>
            <DropdownMenuContent placement="bottom end" className="w-56 p-1.5">
              {canSend && <DropdownMenuItem onAction={() => actions.onReply(message, "reply")} className="px-3 py-2"><ReplyIcon />Reply</DropdownMenuItem>}
              {canSend && many && <DropdownMenuItem onAction={() => actions.onReply(message, "reply_all")} className="px-3 py-2"><ReplyAllIcon />Reply all</DropdownMenuItem>}
              {canSend && <DropdownMenuItem onAction={() => actions.onReply(message, "forward")} className="px-3 py-2"><ForwardIcon />Forward</DropdownMenuItem>}
              <DropdownMenuItem onAction={() => actions.onShowOriginal(message)} className="px-3 py-2"><CodeIcon />Show original</DropdownMenuItem>
              {message.can_unsubscribe && canSend && <DropdownMenuItem onAction={() => actions.onUnsubscribe(message)} className="px-3 py-2"><UnsubscribeIcon />Unsubscribe</DropdownMenuItem>}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      {message.remote_images > 0 && !allowed && (
        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-card-border bg-background-gray-secondary_alt/50 px-3 py-2 text-xs text-text-secondary sm:ml-[52px]">
          <ImageIcon size={16} className="text-icon-tertiary" />
          <span>Images hidden to protect privacy.</span>
          <button type="button" className="font-medium text-primary-600 hover:underline dark:text-primary-300" onClick={() => actions.onShowImages(message, false)}>Show images</button>
          {from && <button type="button" className="font-medium text-primary-600 hover:underline dark:text-primary-300" onClick={() => actions.onShowImages(message, true)}>Always show from {from.email}</button>}
        </div>
      )}
      {message.link_warnings.length > 0 && (
        <div role="note" className="mt-3 flex items-start gap-2 rounded-lg border border-warning-500/40 bg-warning-500/10 px-3 py-2 text-xs text-text-primary sm:ml-[52px]">
          <WarningIcon size={16} className="mt-px shrink-0 text-warning-500" />
          <span>Be careful with links in this message: {message.link_warnings.length === 1 ? "one link shows" : `${message.link_warnings.length} links show`} a different address than where it really goes. Highlighted links are suspicious.</span>
        </div>
      )}

      <div className="mt-3 sm:pl-[52px]">
        <EmailFrame html={message.body_html} title={`Message from ${displayName(from)}`} imagesAllowed={allowed} />
        <Attachments items={message.attachments} />
        {message.can_unsubscribe && canSend && last && (
          <button type="button" onClick={() => actions.onUnsubscribe(message)} className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-text-tertiary hover:text-text-primary hover:underline">
            <UnsubscribeIcon size={14} /> Unsubscribe from this sender
          </button>
        )}
      </div>
    </article>
  );
}
