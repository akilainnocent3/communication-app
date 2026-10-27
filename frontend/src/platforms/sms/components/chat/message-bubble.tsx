"use client";

import { memo, useRef, useState } from "react";
import { toast } from "sonner";
import { Popover } from "@/components/tailgrids/core/popover";
import { CheckIcon, ClockIcon, DoubleCheckIcon, ErrorIcon, EyeIcon, LockIcon, RefreshIcon, StarIcon, WarningIcon } from "@/components/ui/icons";
import { m } from "@/i18n";
import { formatInTimeZone } from "date-fns-tz";
import { fullDate, timezone } from "@/lib/format";
import { errorMessage, mutate } from "@/services/api/client";
import type { SmsMessage } from "@/services/api/types";
import { cn } from "@/utils/cn";
import { LinkifiedText } from "../../lib/linkify";

const PENDING = new Set(["queued", "dispatched", "sending"]);

export function statusLabel(status: string): string {
  return (m.sms.status as Record<string, string>)[status] ?? status;
}

export function StatusIcon({ status, className }: { status: string; className?: string }) {
  const label = statusLabel(status);
  const icon = status === "delivered" ? <DoubleCheckIcon size={14} />
    : status === "sent" ? <CheckIcon size={14} />
      : PENDING.has(status) ? <ClockIcon size={13} />
        : status === "failed" || status === "expired" ? <ErrorIcon size={13} />
          : status === "unknown" ? <WarningIcon size={13} /> : null;
  if (!icon) return null;
  return <span className={cn("inline-flex", className)} title={label}>{icon}<span className="sr-only">{label}</span></span>;
}

type Props = {
  message: SmsMessage;
  deviceName: string;
  canReveal: boolean;
  canSend: boolean;
  showSim: boolean;
  onRetry: (message: SmsMessage) => void;
  onCancel: (message: SmsMessage) => void;
};

function MediaPart({ message, part }: { message: SmsMessage; part: SmsMessage["parts"][number] }) {
  const url = `/api/v1/sms/messages/${message.id}/media/${part.id}/`;
  if (!part.available) return <p className="text-xs italic opacity-80">{m.sms.chat.notArrived}</p>;
  if (part.content_type.startsWith("image/")) {
    return (
      <a href={url} target="_blank" rel="noopener noreferrer" className="block overflow-hidden rounded-xl">
        {/* eslint-disable-next-line @next/next/no-img-element -- authenticated, same-origin media endpoint */}
        <img src={url} alt={part.filename || m.sms.chat.attachment} loading="lazy" className="max-h-72 w-auto max-w-full object-contain" />
      </a>
    );
  }
  if (part.content_type.startsWith("video/")) return <video src={url} controls preload="metadata" className="max-h-72 max-w-full rounded-xl" />;
  if (part.content_type.startsWith("audio/")) return <audio src={url} controls preload="none" className="max-w-full" />;
  return <a href={`${url}?download=1`} className="text-xs underline">{part.filename || m.sms.chat.attachment}</a>;
}

function MessageBubbleBase({ message, deviceName, canReveal, canSend, showSim, onRetry, onCancel }: Props) {
  const outbound = message.direction === "out";
  const admin = message.origin === "admin";
  const [revealed, setRevealed] = useState<string | null>(null);
  const [details, setDetails] = useState(false);
  const anchor = useRef<HTMLButtonElement>(null);
  const body = revealed ?? message.body;

  const reveal = async () => {
    try { setRevealed((await mutate<{ body: string }>(`sms/messages/${message.id}/reveal/`, "POST")).body); }
    catch (error) { toast.error(errorMessage(error)); }
  };

  const time = formatInTimeZone(new Date(message.at), timezone(), "HH:mm");
  return (
    <div className={cn("group flex w-full flex-col", outbound ? "items-end" : "items-start")} data-message-id={message.id} data-status={message.status} data-origin={message.origin}>
      {outbound && (
        <span className={cn("mb-0.5 px-2 text-[11px] font-medium", admin ? "text-[#0f766e] dark:text-[#5eead4]" : "text-text-tertiary")}>
          {admin ? m.sms.chat.admin(message.sent_by?.display_name ?? "") : m.sms.chat.phone}
        </span>
      )}
      <div
        className={cn(
          "max-w-[min(85%,34rem)] rounded-2xl px-3.5 py-2 text-left text-sm leading-relaxed whitespace-pre-wrap break-words shadow-xs",
          !outbound && "rounded-bl-md bg-background-gray-secondary_alt text-text-primary dark:bg-white/8",
          outbound && !admin && "rounded-br-md bg-primary-500 text-white",
          outbound && admin && "rounded-br-md bg-[#0f766e] text-white dark:bg-[#115e59]",
          PENDING.has(message.status) && "opacity-80",
          (message.status === "failed" || message.status === "expired") && "ring-2 ring-error-500/60",
          message.deleted_on_device_at && "opacity-60",
        )}
      >
        {message.parts.length > 0 && <span className="mb-1.5 flex flex-col gap-1.5">{message.parts.map((part) => <MediaPart key={part.id} message={message} part={part} />)}</span>}
        {message.is_masked && !revealed ? (
          <span className="flex flex-col gap-1">
            <span className="flex items-center gap-1.5 text-xs font-medium opacity-80"><LockIcon size={12} />{m.sms.chat.sensitive}</span>
            <span className="tracking-wide">{body}</span>
          </span>
        ) : body ? <LinkifiedText text={body} /> : null}
      </div>
      <div className={cn("mt-0.5 flex items-center gap-1.5 px-2 text-[11px] text-text-tertiary", outbound ? "flex-row-reverse" : "flex-row")}>
        <button ref={anchor} type="button" onClick={() => setDetails(true)} aria-label={`${m.sms.chat.details}: ${statusLabel(message.status)}, ${fullDate(message.at)}`}
          className="rounded hover:text-text-primary hover:underline focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none">
          <time dateTime={message.at}>{time}</time>
        </button>
        {showSim && message.sim && <span className="rounded px-1 font-medium" style={{ color: message.sim.colour }}>{message.sim.label}</span>}
        {outbound && <StatusIcon status={message.status} className={message.status === "delivered" ? "text-primary-500" : message.status === "failed" ? "text-error-500" : ""} />}
        {message.is_starred && <StarIcon size={12} fill="currentColor" className="text-warning-500" />}
        {message.deleted_on_device_at && <span className="italic">{m.sms.chat.deletedOnPhone}</span>}
        {message.is_masked && !revealed && (canReveal
          ? <button type="button" onClick={reveal} className="inline-flex items-center gap-1 font-medium text-primary-600 hover:underline dark:text-primary-300" title={m.sms.chat.revealHint}><EyeIcon size={12} />{m.sms.chat.reveal}</button>
          : <span title={m.sms.chat.noReveal}><LockIcon size={12} /></span>)}
      </div>
      {outbound && admin && PENDING.has(message.status) && (
        <p className="mt-0.5 flex items-center gap-1.5 px-2 text-[11px] text-text-secondary" role="status">
          {message.status === "queued" ? m.sms.chat.waiting(deviceName) : statusLabel(message.status)}
          {message.status === "queued" && canSend && <button type="button" onClick={() => onCancel(message)} className="font-medium text-primary-600 hover:underline dark:text-primary-300">{m.sms.chat.cancel}</button>}
        </p>
      )}
      {outbound && admin && message.status === "unknown" && <p className="mt-0.5 px-2 text-[11px] text-warning-700 dark:text-warning-300">{m.sms.chat.unknown}</p>}
      {outbound && admin && (message.status === "failed" || message.status === "expired") && (
        <p className="mt-0.5 flex items-center gap-1.5 px-2 text-[11px] text-error-600 dark:text-error-400">
          {message.error_detail || statusLabel(message.status)}
          {canSend && <button type="button" onClick={() => onRetry(message)} className="inline-flex items-center gap-1 font-medium text-primary-600 hover:underline dark:text-primary-300"><RefreshIcon size={12} />{m.sms.chat.retry}</button>}
        </p>
      )}
      <Popover triggerRef={anchor} isOpen={details} onOpenChange={setDetails} placement={outbound ? "left top" : "right top"} className="w-72 p-4">
        <h3 className="text-sm font-semibold text-text-primary">{m.sms.chat.details}</h3>
        <dl className="mt-2 space-y-1 text-xs">
          <div className="flex justify-between gap-3"><dt className="text-text-tertiary">{outbound ? "To" : "From"}</dt><dd className="text-right text-text-primary">{message.address}</dd></div>
          <div className="flex justify-between gap-3"><dt className="text-text-tertiary">{outbound ? "Sent by" : "Received"}</dt><dd className="text-right text-text-primary">{outbound ? (admin ? message.sent_by?.display_name : m.sms.chat.phone) : fullDate(message.at)}</dd></div>
          {message.sim && <div className="flex justify-between gap-3"><dt className="text-text-tertiary">SIM</dt><dd className="text-text-primary">{message.sim.label}</dd></div>}
          <div className="flex justify-between gap-3"><dt className="text-text-tertiary">Size</dt><dd className="text-text-primary">{message.segments} SMS · {message.encoding === "ucs2" ? "Unicode" : "GSM-7"}</dd></div>
        </dl>
        {outbound && message.status_history.length > 0 && (
          <ol className="mt-3 space-y-1.5 border-l border-card-border pl-3" aria-label="Status timeline">
            {message.status_history.map((entry, index) => (
              <li key={`${entry.status}-${index}`} className="relative text-xs before:absolute before:top-1.5 before:-left-[15.5px] before:size-2 before:rounded-full before:bg-primary-500">
                <span className="font-medium text-text-primary">{statusLabel(entry.status)}</span> <span className="text-text-tertiary">{fullDate(entry.at)}</span>
              </li>
            ))}
          </ol>
        )}
      </Popover>
    </div>
  );
}

export const MessageBubble = memo(MessageBubbleBase);
