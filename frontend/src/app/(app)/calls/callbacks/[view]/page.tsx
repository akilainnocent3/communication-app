"use client";

import { notFound, useParams } from "next/navigation";
import { useState } from "react";
import { usePageTitle } from "@/components/shell/trail";
import { Button } from "@/components/tailgrids/core/button";
import { EmptyState } from "@/components/ui/empty-state";
import { CallbackIcon, PlusIcon } from "@/components/ui/icons";
import { Page, PageHeader } from "@/components/ui/page";
import { RequestState } from "@/components/ui/request-state";
import { SectionCard } from "@/components/ui/section-card";
import { StatusPill, type Tone } from "@/components/ui/status-pill";
import { m } from "@/i18n";
import { dateTime } from "@/lib/format";
import { errorMessage } from "@/services/api/client";
import type { CallbackView } from "@/platforms/calls/api/keys";
import { useBulkCallbacks, useCallbackAction } from "@/platforms/calls/api/actions";
import { useCallbacks, useCallsDevices, useCallsScope } from "@/platforms/calls/api/queries";
import { CallbackDialog, type CallbackSeed } from "@/platforms/calls/components/callback-dialog";

const VIEWS: CallbackView[] = ["open", "mine", "done"];
const TONE: Record<string, Tone> = { open: "warning", notified: "info", dialed: "info", done: "success", cancelled: "neutral", expired: "neutral" };
const PRIORITY_TONE: Record<string, Tone> = { low: "neutral", normal: "neutral", high: "warning", urgent: "error" };

export default function CallbacksPage() {
  const { view } = useParams<{ view: string }>();
  if (!VIEWS.includes(view as CallbackView)) notFound();
  return <Callbacks key={view} view={view as CallbackView} />;
}

function Callbacks({ view }: { view: CallbackView }) {
  const title = m.calls.callbacks[view];
  usePageTitle({ page: title, section: "Calls" });
  const [scope] = useCallsScope();
  const devices = useCallsDevices();
  const list = useCallbacks(view, scope);
  const action = useCallbackAction();
  const bulk = useBulkCallbacks();
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [seed, setSeed] = useState<CallbackSeed | null>(null);
  const [target, setTarget] = useState("");
  const rows = list.data ?? [];
  const canCreate = devices.some((d) => d.permissions.assign);
  const toggle = (id: number) => setSelected((current) => { const next = new Set(current); if (next.has(id)) next.delete(id); else next.add(id); return next; });

  return (
    <Page wide key={scope}>
      <PageHeader eyebrow="Call-backs" title={title} description="Admins ask a phone's holder to call a customer back. The phone shows it; the holder taps Call."
        actions={canCreate ? <Button onPress={() => setSeed({ device: scope === "all" ? undefined : scope })}><PlusIcon size={16} />{m.calls.createCallback}</Button> : undefined} />
      {selected.size > 0 && view !== "done" && (
        <SectionCard padding="sm" className="mb-3">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="font-medium text-text-primary">{selected.size} selected</span>
            <select aria-label="Move to phone" value={target} onChange={(e) => setTarget(e.target.value)} className="h-9 rounded-lg border border-card-border bg-card-surface-area px-2 text-sm">
              <option value="">Move to phone…</option>
              {devices.filter((d) => d.permissions.assign).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
            <Button size="sm" appearance="outline" isDisabled={!target} onPress={() => bulk.mutateAsync({ ids: [...selected], action: "assign", device: target }).then(() => setSelected(new Set()))}>Move</Button>
            <Button size="sm" appearance="outline" onPress={() => bulk.mutateAsync({ ids: [...selected], action: "done" }).then(() => setSelected(new Set()))}>Mark done</Button>
            <Button size="sm" variant="danger" appearance="outline" onPress={() => bulk.mutateAsync({ ids: [...selected], action: "cancel" }).then(() => setSelected(new Set()))}>Cancel</Button>
          </div>
        </SectionCard>
      )}
      {list.isPending ? <RequestState loading variant="table" onRetry={() => list.refetch()} /> : list.error && !rows.length ? (
        <RequestState loading={false} error={errorMessage(list.error)} onRetry={() => list.refetch()} />
      ) : rows.length === 0 ? (
        <SectionCard><EmptyState icon={<CallbackIcon />} title={m.calls.empty.callbacks.title} body={m.calls.empty.callbacks.body} /></SectionCard>
      ) : (
        <SectionCard padding="none">
          <ul className="divide-y divide-card-border" data-callbacks={view}>
            {rows.map((task) => (
              <li key={task.id} data-callback={task.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                {view !== "done" && <input type="checkbox" aria-label={`Select call-back to ${task.name || task.display_number}`} checked={selected.has(task.id)} onChange={() => toggle(task.id)} />}
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-text-primary">
                    <span className="truncate">{task.name || task.display_number}</span>
                    {task.name && <span className="font-normal text-text-tertiary">{task.display_number}</span>}
                    <StatusPill tone={PRIORITY_TONE[task.priority]}>{m.calls.priority[task.priority]}</StatusPill>
                  </p>
                  <p className="truncate text-xs text-text-tertiary">{task.reason || "No reason given"} · {task.device.name} · asked by {task.assigned_by || "—"}</p>
                </div>
                <div className="text-right text-xs text-text-tertiary">
                  <StatusPill tone={TONE[task.state]}>{m.calls.callbackState[task.state]}</StatusPill>
                  <p className="mt-1">{task.state === "done" && task.done_at ? `Done ${dateTime(task.done_at)}` : `Due ${dateTime(task.due_at)}`}{task.attempts ? ` · ${task.attempts} attempts` : ""}</p>
                </div>
                {view !== "done" && <Button size="xs" appearance="ghost" onPress={() => action.mutateAsync({ id: task.id, action: "cancel" })}>Cancel</Button>}
              </li>
            ))}
          </ul>
        </SectionCard>
      )}
      <CallbackDialog key={seed ? JSON.stringify(seed) : "none"} seed={seed} onClose={() => setSeed(null)} />
    </Page>
  );
}
