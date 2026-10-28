"use client";

import Link from "next/link";
import { useState } from "react";
import { SheetContent, SheetOverlay, SheetTitle } from "@/components/tailgrids/core/sheet";
import { Button } from "@/components/tailgrids/core/button";
import { RequestState } from "@/components/ui/request-state";
import { CallbackIcon, MessageIcon, PhoneIcon, TrashIcon } from "@/components/ui/icons";
import { Chip, StatusPill } from "@/components/ui/status-pill";
import { m } from "@/i18n";
import { dateTime } from "@/lib/format";
import { errorMessage } from "@/services/api/client";
import type { CallDetail } from "@/services/api/types";
import { useAnnotate, useDeleteAnnotation } from "../api/actions";
import { useCall, useOutcomes } from "../api/queries";
import { DirectionIcon, callTitle, duration, isMissed, resultLabel, resultTone } from "../lib/labels";
import type { CallbackSeed } from "./callback-dialog";

function Facts({ call }: { call: CallDetail }) {
  const rows: [string, string][] = [
    ["When", dateTime(call.started_at)], ["Phone", `${call.device.name} · ${call.device.office}`], ["SIM", call.sim?.label ?? "—"],
    ["Ringing", duration(call.ring_seconds)], ["Talk time", duration(call.talk_seconds)],
    ["Ended by", call.ended_by ? { local: "This phone", remote: "The other side", system: "Network" }[call.ended_by] ?? call.ended_by : "—"],
    ["Network", { volte: "VoLTE", wifi: "Wi-Fi calling", cs: "Mobile network", unknown: "—" }[call.network] ?? call.network],
    ["Origin", m.calls.origin[call.origin] ?? call.origin],
  ];
  if (call.was_on_hold_seconds) rows.push(["On hold", duration(call.was_on_hold_seconds)]);
  if (call.is_conference) rows.push(["Conference", `${call.conference_size || 3} people`]);
  if (call.disconnect_cause_label) rows.push(["Disconnect cause", call.disconnect_cause_label]);
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
      {rows.map(([label, value]) => <div key={label} className="min-w-0"><dt className="text-xs text-text-tertiary">{label}</dt><dd className="truncate text-text-primary">{value}</dd></div>)}
    </dl>
  );
}

function Notes({ call }: { call: CallDetail }) {
  const outcomes = useOutcomes();
  const annotate = useAnnotate(call.id);
  const remove = useDeleteAnnotation(call.id);
  const [outcome, setOutcome] = useState<number | null>(null);
  const [note, setNote] = useState("");
  return (
    <section aria-labelledby="call-notes">
      <h3 id="call-notes" className="mb-2 text-xs font-semibold tracking-wider text-text-tertiary uppercase">Outcome and notes</h3>
      {call.outcome_required && !call.annotations.some((a) => a.outcome) && <p className="mb-2 text-xs text-warning-600">An outcome is required for calls this long.</p>}
      <ul className="mb-3 space-y-2">
        {call.annotations.map((a) => (
          <li key={a.id} className="rounded-lg border border-card-border p-2.5 text-sm">
            <div className="flex items-center gap-2">
              {a.outcome && <Chip style={{ borderColor: a.outcome.colour, color: a.outcome.colour }}>{a.outcome.name}</Chip>}
              <span className="text-xs text-text-tertiary">{a.author} · {dateTime(a.created_at)}</span>
              {!a.from_phone && call.permissions.annotate && (
                <Button size="xs" appearance="ghost" iconOnly aria-label="Delete note" className="ml-auto" onPress={() => remove.mutateAsync(a.id)}><TrashIcon /></Button>
              )}
            </div>
            {a.note && <p className="mt-1 whitespace-pre-wrap text-text-primary">{a.note}</p>}
          </li>
        ))}
        {call.annotations.length === 0 && <li className="text-sm text-text-tertiary">No notes yet.</li>}
      </ul>
      {call.permissions.annotate && (
        <form className="space-y-2" onSubmit={(event) => {
          event.preventDefault();
          annotate.mutate({ outcome, note }, { onSuccess: () => { setNote(""); setOutcome(null); } });
        }}>
          <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Outcome">
            {(outcomes.data ?? []).filter((o) => o.is_active).map((o) => (
              <button key={o.id} type="button" role="radio" aria-checked={outcome === o.id} onClick={() => setOutcome(outcome === o.id ? null : o.id!)}
                className="rounded-full border px-2.5 py-1 text-xs font-medium transition-colors focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none"
                style={outcome === o.id ? { background: o.colour, borderColor: o.colour, color: "white" } : { borderColor: o.colour, color: o.colour }}>{o.name}</button>
            ))}
          </div>
          <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={2000} placeholder="Add a note (encrypted)" aria-label="Note"
            className="w-full rounded-lg border border-card-border bg-card-surface-area px-3 py-2 text-sm text-text-primary focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none" />
          <Button type="submit" size="sm" isPending={annotate.isPending} isDisabled={!outcome && !note.trim()}>Save note</Button>
        </form>
      )}
    </section>
  );
}

/** Call detail as a side sheet: facts, timeline, notes, the customer's other calls and messages, "Create call-back". */
export function CallDrawer({ id, onClose, onCallback }: { id: number | null; onClose: () => void; onCallback: (seed: CallbackSeed) => void }) {
  const call = useCall(id);
  const data = call.data;
  return (
    <SheetOverlay isOpen={id !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="w-full max-w-lg! overflow-y-auto border-l border-card-border bg-card-surface-area p-0" aria-label="Call details">
        <div className="space-y-5 p-5" data-call-detail={id ?? undefined}>
          {!data ? <RequestState loading={call.isPending} error={call.error ? errorMessage(call.error) : undefined} onRetry={() => call.refetch()} /> : (
            <>
              <header className="flex items-start gap-3 pr-8">
                <DirectionIcon call={data} size={22} className="mt-1" />
                <div className="min-w-0">
                  <SheetTitle className="truncate text-lg font-semibold text-text-primary">{callTitle(data)}</SheetTitle>
                  <p className="text-sm text-text-tertiary">{data.name ? data.display_number : ""}{data.name_source ? ` · ${data.name_source === "directory" ? m.calls.nameFromDirectory : m.calls.nameFromPhone}` : ""}</p>
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    <StatusPill tone={resultTone(data)}>{data.is_final ? resultLabel(data.result) : m.calls.ringing}</StatusPill>
                    {data.is_after_hours && <StatusPill tone="neutral">After hours</StatusPill>}
                    {isMissed(data) && <StatusPill tone={data.returned_at ? "success" : "warning"}>{data.returned_at ? `Returned ${dateTime(data.returned_at)}` : "Not returned yet"}</StatusPill>}
                    {data.deleted_on_device && <StatusPill tone="neutral">{m.calls.deletedOnPhone}</StatusPill>}
                  </div>
                </div>
              </header>
              <div className="flex flex-wrap gap-2">
                {data.permissions.assign && data.number && (
                  <Button size="sm" onPress={() => onCallback({ device: data.device.id, call: data.id, title: callTitle(data) })}><CallbackIcon size={16} />{m.calls.createCallback}</Button>
                )}
                {data.customer_id && <Link href={`/calls/customers/${data.customer_id}`} className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-card-border px-3 text-sm font-medium text-text-primary hover:bg-background-gray-secondary_alt">Customer page</Link>}
              </div>
              <Facts call={data} />
              {data.events.length > 0 && (
                <section aria-labelledby="call-timeline">
                  <h3 id="call-timeline" className="mb-2 text-xs font-semibold tracking-wider text-text-tertiary uppercase">Timeline</h3>
                  <ol className="space-y-1.5 border-l border-card-border pl-3 text-sm">
                    {data.events.map((event) => <li key={`${event.kind}-${event.at}`}><span className="font-medium text-text-primary capitalize">{event.kind.replace("_", " ")}</span> <span className="text-text-tertiary">{dateTime(event.at)}</span></li>)}
                  </ol>
                </section>
              )}
              <Notes call={data} />
              <section aria-labelledby="call-history">
                <h3 id="call-history" className="mb-2 text-xs font-semibold tracking-wider text-text-tertiary uppercase">Customer history</h3>
                {data.history.length === 0 ? <p className="text-sm text-text-tertiary">No other calls or messages.</p> : (
                  <ul className="divide-y divide-card-border rounded-lg border border-card-border">
                    {data.history.map((item) => (
                      <li key={`${item.kind}-${item.call_id ?? item.conversation_id}-${item.at}`} className="flex items-center gap-2 px-3 py-2 text-sm">
                        {item.kind === "call" ? <PhoneIcon size={15} className="text-icon-tertiary" /> : <MessageIcon size={15} className="text-icon-tertiary" />}
                        {item.kind === "sms" && item.conversation_id
                          ? <Link href={`/sms/inbox?c=${item.conversation_id}`} className="min-w-0 flex-1 truncate text-primary-500 hover:underline">{item.snippet || "Messages"}</Link>
                          : <span className="min-w-0 flex-1 truncate text-text-primary">{m.calls.direction[item.direction as "in" | "out"]} · {resultLabel(item.result)}{item.talk_seconds ? ` · ${duration(item.talk_seconds)}` : ""}</span>}
                        <span className="shrink-0 text-xs text-text-tertiary">{item.device} · {dateTime(item.at)}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
              <p className="text-xs text-text-tertiary">{m.calls.noRecording}</p>
            </>
          )}
        </div>
      </SheetContent>
    </SheetOverlay>
  );
}
