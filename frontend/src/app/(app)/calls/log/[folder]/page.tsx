"use client";

import { notFound, useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useDeferredValue, useMemo, useState } from "react";
import { usePageTitle } from "@/components/shell/trail";
import { Button } from "@/components/tailgrids/core/button";
import { EmptyState } from "@/components/ui/empty-state";
import { PhoneIcon, RefreshIcon, SearchIcon } from "@/components/ui/icons";
import { RequestState } from "@/components/ui/request-state";
import { m } from "@/i18n";
import { errorMessage } from "@/services/api/client";
import type { CallFolder } from "@/platforms/calls/api/keys";
import { useCallList, useCallsScope, useCurrentCallsDevice, useOutcomes } from "@/platforms/calls/api/queries";
import { CallbackDialog, type CallbackSeed } from "@/platforms/calls/components/callback-dialog";
import { CallDrawer } from "@/platforms/calls/components/call-drawer";
import { CallList, CallListSkeleton } from "@/platforms/calls/components/call-list";

const FOLDERS: CallFolder[] = ["all", "missed", "unreturned", "incoming", "outgoing", "after_hours"];
const SELECT = "h-9 rounded-lg border border-card-border bg-card-surface-area px-2 text-sm text-text-primary";

export default function CallLogPage() {
  const { folder } = useParams<{ folder: string }>();
  if (!FOLDERS.includes(folder as CallFolder)) notFound();
  return <Suspense fallback={<CallListSkeleton />}><CallLog key={folder} folder={folder as CallFolder} /></Suspense>;
}

function CallLog({ folder }: { folder: CallFolder }) {
  const title = m.calls.folders[folder];
  usePageTitle({ page: title, section: "Calls" });
  const router = useRouter();
  const params = useSearchParams();
  const [scope] = useCallsScope();
  const current = useCurrentCallsDevice();
  const outcomes = useOutcomes();
  const [q, setQ] = useState("");
  const [result, setResult] = useState("");
  const [outcome, setOutcome] = useState("");
  const [sim, setSim] = useState("");
  const [after, setAfter] = useState("");
  const [before, setBefore] = useState("");
  const [minDuration, setMinDuration] = useState("");
  const search = useDeferredValue(q);
  const listParams = useMemo(() => ({
    device: scope, folder, q: search.trim() || undefined, result: result || undefined, outcome: outcome ? Number(outcome) : undefined, sim: sim ? Number(sim) : undefined,
    after: after || undefined, before: before || undefined, min_duration: minDuration ? Number(minDuration) : undefined,
  }), [scope, folder, search, result, outcome, sim, after, before, minDuration]);
  const list = useCallList(listParams);
  const rows = useMemo(() => list.data?.pages.flatMap((page) => page.results) ?? [], [list.data]);
  const openId = Number(params.get("call")) || null;
  const [callback, setCallback] = useState<CallbackSeed | null>(null);
  const open = (id: number | null) => {
    const next = new URLSearchParams(params.toString());
    if (id) next.set("call", String(id)); else next.delete("call");
    router.replace(`?${next.toString()}`, { scroll: false });
  };

  return (
    <div className="flex h-full min-h-0 flex-col" key={scope} data-calls-log={folder}>
      <div className="border-b border-card-border px-4 pt-4 pb-3 sm:px-5">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div className="min-w-0">
            <h1 className="text-xl font-semibold tracking-tight text-text-primary">{title}</h1>
            <p className="text-sm text-text-tertiary">{m.calls.folderHints[folder]}</p>
          </div>
          <Button appearance="outline" size="sm" aria-label="Refresh" onPress={() => list.refetch()}><RefreshIcon size={16} /></Button>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <label className="relative min-w-48 flex-1 sm:max-w-xs">
            <span className="sr-only">Search calls</span>
            <SearchIcon size={16} className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-icon-tertiary" />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name or number" className="h-9 w-full rounded-lg border border-card-border bg-card-surface-area pr-2 pl-8 text-sm text-text-primary" />
          </label>
          {(folder === "all" || folder === "incoming" || folder === "outgoing" || folder === "after_hours") && (
            <select aria-label="Result" value={result} onChange={(e) => setResult(e.target.value)} className={SELECT}>
              <option value="">Any result</option>
              {Object.entries(m.calls.result).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
            </select>
          )}
          <select aria-label="Outcome" value={outcome} onChange={(e) => setOutcome(e.target.value)} className={SELECT}>
            <option value="">Any outcome</option>
            {(outcomes.data ?? []).map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
          </select>
          {current && current.sims.length > 1 && (
            <select aria-label="SIM" value={sim} onChange={(e) => setSim(e.target.value)} className={SELECT}>
              <option value="">All SIMs</option>
              {current.sims.map((line) => <option key={line.id} value={line.id}>{line.label}</option>)}
            </select>
          )}
          <select aria-label="Duration" value={minDuration} onChange={(e) => setMinDuration(e.target.value)} className={SELECT}>
            <option value="">Any length</option><option value="60">1 min +</option><option value="300">5 min +</option><option value="900">15 min +</option>
          </select>
          <label className="flex items-center gap-1 text-xs text-text-tertiary">From<input type="date" aria-label="From date" value={after} onChange={(e) => setAfter(e.target.value)} className={SELECT} /></label>
          <label className="flex items-center gap-1 text-xs text-text-tertiary">to<input type="date" aria-label="To date" value={before} onChange={(e) => setBefore(e.target.value)} className={SELECT} /></label>
        </div>
      </div>
      {list.isPending ? <CallListSkeleton /> : list.error && !rows.length ? (
        <div className="p-4"><RequestState loading={false} error={errorMessage(list.error)} onRetry={() => list.refetch()} /></div>
      ) : rows.length === 0 ? (
        <EmptyState icon={<PhoneIcon />} title={m.calls.empty.calls.title} body={m.calls.empty.calls.body} />
      ) : (
        <CallList rows={rows} hasMore={!!list.hasNextPage} loadingMore={list.isFetchingNextPage} onLoadMore={() => { if (!list.isFetchingNextPage) list.fetchNextPage(); }}
          activeId={openId} showDevice={scope === "all"} onOpen={(call) => open(call.id)} />
      )}
      <CallDrawer id={openId} onClose={() => open(null)} onCallback={setCallback} />
      <CallbackDialog key={callback ? JSON.stringify(callback) : "none"} seed={callback} onClose={() => setCallback(null)} />
    </div>
  );
}
