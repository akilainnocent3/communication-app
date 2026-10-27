"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Dialog, DialogHeader, DialogTitle } from "@/components/tailgrids/core/dialog";
import { Button } from "@/components/tailgrids/core/button";
import { Popover } from "@/components/tailgrids/core/popover";
import { toast } from "sonner";
import { useSession } from "@/components/shell/session-provider";
import { ClockIcon, SendIcon, TemplateIcon, WarningIcon } from "@/components/ui/icons";
import { controlClass } from "@/components/ui/form";
import { m } from "@/i18n";
import { dateTime } from "@/lib/format";
import { errorMessage, mutate } from "@/services/api/client";
import type { DeviceDetail, SmsComposeRequest, SmsComposeResult, SmsMessage } from "@/services/api/types";
import { cn } from "@/utils/cn";
import { smsKeys } from "../../api/keys";
import { useQuickReplies } from "../../api/queries";
import { segmentInfo, withSignature } from "../../lib/segments";

export type ComposerProps = {
  device: DeviceDetail | undefined;
  conversation?: number;
  to?: string[];
  defaultSim?: number | null;
  canSend: boolean;
  onSent?: (result: SmsComposeResult) => void;
  autoFocus?: boolean;
  /** Recipient field is owned by the parent (new message dialog) and must be valid before sending. */
  recipientsReady?: boolean;
};

function newUuid() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

/** Why sending is disabled, if it is. */
function blockedReason(device: DeviceDetail | undefined, canSend: boolean): string | null {
  if (!canSend) return m.sms.composer.noSend;
  if (device?.status === "suspended") return m.sms.composer.suspended;
  if (device?.status === "revoked") return m.sms.composer.revoked;
  return null;
}

export function Composer({ device, conversation, to, defaultSim, canSend, onSent, autoFocus, recipientsReady = true }: ComposerProps) {
  const client = useQueryClient();
  const { preferences } = useSession();
  const [text, setText] = useState("");
  const [sim, setSim] = useState<number | null>(defaultSim ?? null);
  const [busy, setBusy] = useState(false);
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [when, setWhen] = useState("");
  const [repliesOpen, setRepliesOpen] = useState(false);
  const repliesRef = useRef<HTMLButtonElement>(null);
  const area = useRef<HTMLTextAreaElement>(null);
  const replies = useQuickReplies(device?.id ?? "all");

  const blocked = blockedReason(device, canSend);
  const options = (device?.options ?? {}) as { signature?: string; signature_enabled?: boolean };
  const final = withSignature(text.trim(), options.signature, options.signature_enabled);
  const info = segmentInfo(final);
  const sims = device?.sims ?? [];
  const activeSim = sim ?? defaultSim ?? sims.find((s) => s.is_default)?.id ?? sims[0]?.id ?? null;

  const refresh = () => {
    client.invalidateQueries({ queryKey: smsKeys.conversationLists() });
    if (conversation) client.invalidateQueries({ queryKey: smsKeys.messages(conversation) });
    client.invalidateQueries({ queryKey: ["sms", "outbox"] });
  };

  const submit = async (sendAt?: Date) => {
    if (!device || blocked || !text.trim() || busy || !recipientsReady) return;
    setBusy(true);
    const undoSeconds = sendAt ? undefined : preferences.undo_send_seconds;
    const body: SmsComposeRequest = {
      device: device.id, conversation: conversation ?? null, to: conversation ? [] : to ?? [], body: text.trim(), sim_line: activeSim,
      send_at: sendAt ? sendAt.toISOString() : null, undo_seconds: undoSeconds ?? null, client_uuid: newUuid(),
    };
    try {
      const result = await mutate<SmsComposeResult>("sms/send/", "POST", body);
      const draft = text;
      setText("");
      refresh();
      onSent?.(result);
      if (sendAt) toast.success(m.sms.composer.scheduledFor(dateTime(sendAt)));
      else if (undoSeconds) {
        toast(m.sms.composer.sending(undoSeconds), {
          duration: undoSeconds * 1000,
          action: {
            label: m.common.undo,
            onClick: async () => {
              try {
                await mutate<SmsMessage>(`sms/messages/${result.message.id}/cancel/`, "POST");
                setText(draft);
                refresh();
                toast(m.sms.composer.undone);
              } catch (error) { toast.error(errorMessage(error)); }
            },
          },
        });
      } else toast.success(m.sms.composer.sent);
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(false);
      area.current?.focus();
    }
  };

  const offline = device && device.status === "active" && !device.online;
  const notDefault = device && device.status === "active" && !device.is_default_sms_app && !device.is_simulated;

  if (blocked) {
    return (
      <div role="note" className="flex items-center gap-2 border-t border-card-border bg-background-gray-secondary_alt/40 px-4 py-3 text-sm text-text-secondary" data-sms-composer="disabled">
        <WarningIcon size={16} className="shrink-0 text-warning-500" />{blocked}
      </div>
    );
  }

  return (
    <div className="border-t border-card-border bg-card-surface-area px-3 pt-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] sm:px-4" data-sms-composer="">
      {(offline || notDefault) && (
        <p role="status" className="mb-2 flex items-start gap-2 rounded-lg bg-warning-500/10 px-3 py-2 text-xs text-text-secondary">
          <ClockIcon size={14} className="mt-0.5 shrink-0 text-warning-500" />
          {offline ? m.sms.composer.offline(device!.name) : m.sms.composer.notDefault}
        </p>
      )}
      <div className="flex items-end gap-2">
        <div className="min-w-0 flex-1 rounded-2xl border border-card-border bg-input-background focus-within:border-primary-500 focus-within:ring-4 focus-within:ring-primary-500/15">
          <label htmlFor="sms-composer" className="sr-only">{m.sms.composer.placeholder}</label>
          <textarea
            id="sms-composer" ref={area} value={text} rows={1} autoFocus={autoFocus} maxLength={5000}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); submit(); }
            }}
            placeholder={m.sms.composer.placeholder}
            className="block max-h-40 min-h-11 w-full resize-none bg-transparent px-4 py-3 text-sm text-text-primary outline-none [field-sizing:content] placeholder:text-text-tertiary"
          />
          <div className="flex flex-wrap items-center gap-1 px-2 pb-1.5">
            {sims.length > 1 && (
              <label className="flex items-center gap-1 text-xs text-text-tertiary">
                <span className="sr-only">{m.sms.composer.sim}</span>
                <select value={activeSim ?? ""} onChange={(event) => setSim(Number(event.target.value))} aria-label={m.sms.composer.sim}
                  className="h-7 rounded-full border border-card-border bg-card-surface-area pr-6 pl-2 text-xs text-text-primary">
                  {sims.map((line) => <option key={line.id} value={line.id}>{line.label}</option>)}
                </select>
              </label>
            )}
            <button ref={repliesRef} type="button" onClick={() => setRepliesOpen(true)} aria-label={m.sms.composer.quickReplies} title={m.sms.composer.quickReplies}
              className="flex size-7 items-center justify-center rounded-full text-icon-secondary hover:bg-background-gray-secondary_alt hover:text-text-primary focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none">
              <TemplateIcon size={16} />
            </button>
            <button type="button" onClick={() => setScheduleOpen(true)} aria-label={m.sms.composer.schedule} title={m.sms.composer.schedule} disabled={!text.trim()}
              className="flex size-7 items-center justify-center rounded-full text-icon-secondary hover:bg-background-gray-secondary_alt hover:text-text-primary focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none disabled:opacity-40">
              <ClockIcon size={16} />
            </button>
            <span className={cn("ml-auto text-[11px] tabular-nums", info.segments > 3 ? "text-warning-600 dark:text-warning-400" : "text-text-tertiary")} aria-live="polite" data-segment-counter="">
              {text ? m.sms.composer.segments(info.segments, info.remaining, info.encoding) : ""}
            </span>
          </div>
        </div>
        <button type="button" onClick={() => submit()} disabled={!text.trim() || busy || !recipientsReady} aria-label={m.sms.composer.send}
          className="flex size-11 shrink-0 items-center justify-center rounded-full bg-primary-500 text-white shadow-sm transition hover:bg-primary-600 focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2 focus-visible:outline-none active:scale-95 disabled:opacity-40">
          <SendIcon size={18} />
        </button>
      </div>
      {options.signature_enabled && options.signature && <p className="mt-1 px-2 text-[11px] text-text-tertiary">{m.sms.composer.signature(options.signature)}</p>}

      <Popover triggerRef={repliesRef} isOpen={repliesOpen} onOpenChange={setRepliesOpen} placement="top start" className="w-80 p-1.5">
        {(replies.data ?? []).length === 0 ? <p className="px-3 py-2 text-sm text-text-tertiary">{m.sms.composer.noQuickReplies}</p> : (
          <ul role="listbox" aria-label={m.sms.composer.quickReplies} className="max-h-72 overflow-y-auto">
            {replies.data!.map((reply) => (
              <li key={reply.id}>
                <button type="button" onClick={() => { setText((current) => (current ? `${current} ${reply.body}` : reply.body)); setRepliesOpen(false); area.current?.focus(); }}
                  className="w-full rounded-lg px-3 py-2 text-left hover:bg-background-gray-secondary_alt focus-visible:bg-background-gray-secondary_alt focus-visible:outline-none">
                  <span className="block text-sm font-medium text-text-primary">{reply.title}</span>
                  <span className="line-clamp-2 text-xs text-text-tertiary">{reply.body}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Popover>

      <Dialog isOpen={scheduleOpen} onOpenChange={setScheduleOpen} className="max-w-sm">
        <DialogHeader><DialogTitle>{m.sms.composer.schedule}</DialogTitle></DialogHeader>
        <label className="mt-4 block text-sm">
          <span className="mb-2 block font-medium text-text-primary">Send at</span>
          <input type="datetime-local" value={when} onChange={(event) => setWhen(event.target.value)} className={controlClass} />
        </label>
        <div className="mt-6 flex justify-end gap-2">
          <Button appearance="outline" onPress={() => setScheduleOpen(false)}>{m.common.cancel}</Button>
          <Button isDisabled={!when} onPress={async () => { await submit(new Date(when)); setScheduleOpen(false); setWhen(""); }}>{m.sms.composer.schedule}</Button>
        </div>
      </Dialog>
    </div>
  );
}
