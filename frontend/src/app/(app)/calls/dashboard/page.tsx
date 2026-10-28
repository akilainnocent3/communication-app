"use client";

import Link from "next/link";
import { useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipContentProps } from "recharts";
import type { NameType, ValueType } from "recharts/types/component/DefaultTooltipContent";
import { formatInTimeZone } from "date-fns-tz";
import { usePageTitle } from "@/components/shell/trail";
import { Button } from "@/components/tailgrids/core/button";
import { EmptyState } from "@/components/ui/empty-state";
import { CallIncomingIcon, CallMissedIcon, CallOutgoingIcon, CallbackIcon, ClockIcon, CoinsIcon, MoonClockIcon, PhoneIcon, UsersIcon, WarningIcon } from "@/components/ui/icons";
import { Page, PageHeader } from "@/components/ui/page";
import { PageSkeleton, RequestState } from "@/components/ui/request-state";
import { SectionCard, StatCard } from "@/components/ui/section-card";
import { m } from "@/i18n";
import { compactNumber, listTime, minutesLabel, timezone } from "@/lib/format";
import { errorMessage } from "@/services/api/client";
import type { CallStats } from "@/services/api/types";
import { useCallStats, useCallsScope, useCurrentCallsDevice } from "@/platforms/calls/api/queries";
import { CallbackDialog, type CallbackSeed } from "@/platforms/calls/components/callback-dialog";
import { duration } from "@/platforms/calls/lib/labels";
import { logUrl } from "@/platforms/calls/nav";
import { DeviceAvatar } from "@/platforms/sms/components/device-badges";
import { cn } from "@/utils/cn";

const RANGES = [7, 30, 90] as const;
const SERIES = [
  { key: "incoming", name: "Incoming", colour: "var(--chart-received)", dash: undefined },
  { key: "outgoing", name: "Outgoing", colour: "var(--chart-sent)", dash: undefined },
  { key: "missed", name: "Missed", colour: "var(--chart-missed)", dash: "5 4" },
] as const;
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const dayLabel = (iso: string) => formatInTimeZone(new Date(`${iso}T12:00:00Z`), timezone(), "d MMM");
const pct = (value: number | null) => (value === null ? "—" : `${value}%`);

export default function CallsDashboardPage() {
  usePageTitle({ page: "Dashboard", section: "Calls" });
  const [scope] = useCallsScope();
  const current = useCurrentCallsDevice();
  const [days, setDays] = useState<(typeof RANGES)[number]>(30);
  const [sim, setSim] = useState<number | undefined>();
  const [callback, setCallback] = useState<CallbackSeed | null>(null);
  const stats = useCallStats(scope, days, sim);

  if (stats.isPending) return <Page wide><PageSkeleton /></Page>;
  if (stats.error && !stats.data) return <Page wide><RequestState loading={false} error={errorMessage(stats.error)} onRetry={() => stats.refetch()} /></Page>;
  const data = stats.data!;
  return (
    <Page wide key={scope}>
      <PageHeader eyebrow="Overview" title="Calls dashboard"
        description={scope === "all" ? "Every Calls phone you can open. The numbers match the call log for the same phones and dates." : `${current?.name ?? "This phone"} at a glance.`}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {current && current.sims.length > 1 && (
              <select aria-label="SIM" value={sim ?? ""} onChange={(e) => setSim(e.target.value ? Number(e.target.value) : undefined)} className="h-9 rounded-lg border border-card-border bg-card-surface-area px-2 text-sm text-text-primary">
                <option value="">All SIMs</option>
                {current.sims.map((line) => <option key={line.id} value={line.id}>{line.label}</option>)}
              </select>
            )}
            <div role="radiogroup" aria-label="Date range" className="inline-flex rounded-lg border border-card-border bg-card-surface-area p-0.5">
              {RANGES.map((range) => (
                <button key={range} type="button" role="radio" aria-checked={days === range} onClick={() => setDays(range)}
                  className={cn("h-8 rounded-md px-3 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none", days === range ? "bg-primary-500 text-white" : "text-text-secondary hover:text-text-primary")}>
                  {range} days
                </button>
              ))}
            </div>
          </div>
        } />
      {data.per_device.length === 0 ? (
        <SectionCard><EmptyState icon={<PhoneIcon />} title={m.calls.empty.noDevices.title} body={m.calls.empty.noDevices.body} /></SectionCard>
      ) : (
        <div className={cn("space-y-4 sm:space-y-5", stats.isPlaceholderData && "opacity-70 transition-opacity")} data-calls-dashboard="">
          <Kpis data={data} />
          <div className="grid gap-4 sm:gap-5 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
            <VolumeChart data={data} />
            <Unreturned data={data} onCallback={setCallback} />
          </div>
          <div className="grid gap-4 sm:gap-5 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
            <Heatmap data={data} />
            <Callers data={data} />
          </div>
          <div className="grid gap-4 sm:gap-5 xl:grid-cols-3">
            <Leaderboard title="Offices" rows={data.per_office.map((r) => ({ ...r, key: String(r.id) }))} />
            <Leaderboard title="Phones" rows={data.per_device.map((r) => ({ ...r, key: r.id }))} />
            <Leaderboard title="Staff" rows={data.staff.map((r) => ({ ...r, key: String(r.user_id), colour: "" }))} empty="Assign phones to staff to compare them." />
          </div>
          <div className="grid gap-4 sm:gap-5 xl:grid-cols-2">
            <Outcomes data={data} />
            <Cost data={data} />
          </div>
        </div>
      )}
      <CallbackDialog key={callback ? JSON.stringify(callback) : "none"} seed={callback} onClose={() => setCallback(null)} />
    </Page>
  );
}

function Kpis({ data }: { data: CallStats }) {
  const k = data.kpis;
  return (
    <dl className="grid grid-cols-2 gap-2 sm:gap-3 md:grid-cols-4 2xl:grid-cols-8">
      <StatCard label="Incoming" icon={<CallIncomingIcon size={14} />} value={compactNumber(k.incoming)} hint={`Last ${data.range_days} days`} />
      <StatCard label="Outgoing" icon={<CallOutgoingIcon size={14} />} value={compactNumber(k.outgoing)} hint={`${k.answered_outgoing} reached`} />
      <StatCard label="Missed" icon={<CallMissedIcon size={14} />} value={compactNumber(k.missed)} hint={`${pct(k.missed_rate)} of incoming`} tone={k.missed ? "error" : undefined} />
      <StatCard label="Answer rate" icon={<PhoneIcon size={14} />} value={pct(k.answer_rate)} tone={k.answer_rate !== null && k.answer_rate < 80 ? "warning" : undefined} />
      <StatCard label={`Not called back within ${data.unreturned_hours} h`} icon={<WarningIcon size={14} />} value={k.unreturned} tone={k.unreturned ? "warning" : undefined}
        hint={k.unreturned_open ? `${k.unreturned_open} still within ${data.unreturned_hours} h` : <Link href={logUrl("unreturned")} className="font-medium text-primary-500 hover:underline">Open list</Link>} />
      <StatCard label="Median time to call back" icon={<CallbackIcon size={14} />} value={minutesLabel(k.median_callback_minutes)} />
      <StatCard label="Talk time (avg · median)" icon={<ClockIcon size={14} />} value={`${duration(k.avg_talk_seconds)} · ${duration(k.median_talk_seconds)}`} hint={`${compactNumber(k.talk_minutes)} min in total`} />
      <StatCard label="Ring before answer" icon={<ClockIcon size={14} />} value={duration(k.avg_ring_seconds)} hint={`${k.abandoned} hung up while ringing`} />
      <StatCard label="After hours" icon={<MoonClockIcon size={14} />} value={k.after_hours} hint={`${k.after_hours_missed} missed`} />
      <StatCard label="Unique callers" icon={<UsersIcon size={14} />} value={data.callers.unique} hint={`${pct(data.callers.repeat_rate)} called again`} />
      <StatCard label="First-time callers" icon={<UsersIcon size={14} />} value={data.callers.first_time} hint={`${data.callers.returning} returning`} />
      <StatCard label="Called and texted" icon={<UsersIcon size={14} />} value={data.callers.called_and_texted} hint="Customers on both channels" />
    </dl>
  );
}

function ChartTooltip({ active, payload, label }: TooltipContentProps<ValueType, NameType>) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-card-border bg-card-surface-area px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 font-medium text-text-primary">{dayLabel(String(label))}</p>
      {SERIES.map((series) => (
        <p key={series.key} className="flex items-center gap-2 text-text-secondary">
          <span className="size-2 rounded-full" style={{ background: series.colour }} aria-hidden="true" />{series.name}
          <span className="ml-auto pl-3 font-semibold tabular-nums text-text-primary">{payload.find((entry) => entry.dataKey === series.key)?.value ?? 0}</span>
        </p>
      ))}
    </div>
  );
}

function VolumeChart({ data }: { data: CallStats }) {
  const [asTable, setAsTable] = useState(false);
  const totals = { incoming: data.kpis.incoming, outgoing: data.kpis.outgoing, missed: data.kpis.missed };
  return (
    <SectionCard title="Calls per day" description={`Incoming, outgoing and missed, last ${data.range_days} days`}
      actions={<button type="button" onClick={() => setAsTable((v) => !v)} className="text-xs font-medium text-primary-500 hover:underline">{asTable ? "View chart" : "View as table"}</button>}>
      <ul className="mb-3 flex flex-wrap gap-4 text-xs text-text-secondary" aria-label="Legend">
        {SERIES.map((series) => (
          <li key={series.key} className="flex items-center gap-2">
            <svg width="16" height="4" aria-hidden="true"><line x1="0" y1="2" x2="16" y2="2" stroke={series.colour} strokeWidth="2" strokeDasharray={series.dash} /></svg>
            {series.name} <span className="font-semibold tabular-nums text-text-primary">{compactNumber(totals[series.key])}</span>
          </li>
        ))}
      </ul>
      {asTable ? (
        <div className="max-h-72 overflow-auto rounded-lg border border-card-border">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-card-surface-area text-left text-xs text-text-tertiary"><tr><th className="px-3 py-2 font-medium">Day</th>{SERIES.map((s) => <th key={s.key} className="px-3 py-2 text-right font-medium">{s.name}</th>)}</tr></thead>
            <tbody className="divide-y divide-card-border">{[...data.series].reverse().map((row) => <tr key={row.date}><td className="px-3 py-1.5 text-text-secondary">{dayLabel(row.date)}</td>{SERIES.map((s) => <td key={s.key} className="px-3 py-1.5 text-right tabular-nums">{row[s.key]}</td>)}</tr>)}</tbody>
          </table>
        </div>
      ) : (
        <div className="h-64 sm:h-72" role="img" aria-label={`Line chart: ${totals.incoming} incoming, ${totals.outgoing} outgoing and ${totals.missed} missed calls`}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data.series} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
              <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
              <XAxis dataKey="date" tickFormatter={dayLabel} tickLine={false} axisLine={false} minTickGap={24} tick={{ fill: "var(--text-tertiary)", fontSize: 11 }} />
              <YAxis allowDecimals={false} tickLine={false} axisLine={false} width={44} tick={{ fill: "var(--text-tertiary)", fontSize: 11 }} />
              <Tooltip content={ChartTooltip} cursor={{ stroke: "var(--text-tertiary)", strokeDasharray: "3 3" }} />
              {SERIES.map((s) => <Line key={s.key} type="monotone" dataKey={s.key} name={s.name} stroke={s.colour} strokeWidth={2} strokeDasharray={s.dash} dot={false} isAnimationActive={false} />)}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </SectionCard>
  );
}

function Unreturned({ data, onCallback }: { data: CallStats; onCallback: (seed: CallbackSeed) => void }) {
  return (
    <SectionCard title="Waiting for a call back" description={`Missed calls nobody has returned yet`} actions={<Link href={logUrl("unreturned")} className="text-xs font-medium text-primary-500 hover:underline">All</Link>}>
      {data.unreturned_list.length === 0 ? <EmptyState compact icon={<CallbackIcon />} title="Everyone was called back" body="No missed call is waiting." /> : (
        <ul className="divide-y divide-card-border" data-unreturned-list="">
          {data.unreturned_list.map((row) => (
            <li key={row.id} className="flex items-center gap-2 py-2 text-sm">
              <CallMissedIcon size={16} className="shrink-0 text-error-500" />
              <span className="min-w-0 flex-1">
                <span className="block truncate font-medium text-text-primary">{row.name || row.display || m.calls.privateNumber}</span>
                <span className="block truncate text-xs text-text-tertiary">{row.device} · {listTime(row.started_at)}</span>
              </span>
              <Button size="xs" appearance="outline" onPress={() => onCallback({ device: row.device_id, call: row.id, title: row.name || row.display })}>Call back</Button>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}

function Heatmap({ data }: { data: CallStats }) {
  const max = Math.max(1, ...data.heatmap.flat());
  return (
    <SectionCard title="Busiest hours" description="Incoming calls by weekday and hour (your time zone)">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] border-separate border-spacing-0.5 text-[10px]" aria-label="Incoming calls by weekday and hour">
          <thead><tr><th className="w-8" />{Array.from({ length: 24 }, (_, h) => <th key={h} scope="col" className="font-normal text-text-tertiary">{h % 3 === 0 ? h : ""}</th>)}</tr></thead>
          <tbody>
            {data.heatmap.map((row, day) => (
              <tr key={DAYS[day]}>
                <th scope="row" className="pr-1 text-left font-medium text-text-tertiary">{DAYS[day]}</th>
                {row.map((value, hour) => (
                  <td key={hour} title={`${DAYS[day]} ${hour}:00 — ${value} calls`} className="h-5 rounded-sm"
                    style={{ background: value ? `color-mix(in oklab, var(--chart-received) ${Math.round(15 + (value / max) * 85)}%, transparent)` : "var(--chart-grid)" }}>
                    <span className="sr-only">{value}</span>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </SectionCard>
  );
}

function Callers({ data }: { data: CallStats }) {
  const max = Math.max(1, ...data.top_callers.map((c) => c.incoming));
  return (
    <SectionCard title="Top callers" description={`Who called most, last ${data.range_days} days`}>
      {data.top_callers.length === 0 ? <p className="py-6 text-center text-sm text-text-tertiary">No incoming calls in this period.</p> : (
        <ol className="space-y-2.5">
          {data.top_callers.map((caller) => (
            <li key={caller.number} className="min-w-0">
              <div className="flex items-baseline justify-between gap-3 text-sm">
                {caller.customer_id ? <Link href={`/calls/customers/${caller.customer_id}`} className="min-w-0 truncate text-text-primary hover:underline">{caller.name || caller.display}</Link>
                  : <span className="min-w-0 truncate text-text-primary">{caller.name || caller.display}</span>}
                <span className="shrink-0 tabular-nums text-text-secondary">{caller.incoming}{caller.missed ? <span className="text-error-500"> · {caller.missed} missed</span> : null}</span>
              </div>
              <div className="mt-1 h-1.5 rounded-full bg-background-gray-secondary_alt" aria-hidden="true"><div className="h-full rounded-full bg-[var(--chart-received)]" style={{ width: `${(caller.incoming / max) * 100}%` }} /></div>
            </li>
          ))}
        </ol>
      )}
    </SectionCard>
  );
}

type Board = { key: string; name: string; colour: string; calls: number; missed: number; answer_rate: number | null; talk_minutes: number };

function Leaderboard({ title, rows, empty }: { title: string; rows: Board[]; empty?: string }) {
  return (
    <SectionCard title={title} padding="sm">
      {rows.length === 0 ? <p className="py-6 text-center text-sm text-text-tertiary">{empty ?? "No calls in this period."}</p> : (
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-text-tertiary"><tr><th className="py-1.5 font-medium">Name</th><th className="py-1.5 text-right font-medium">Calls</th><th className="py-1.5 text-right font-medium">Missed</th><th className="py-1.5 text-right font-medium">Answered</th><th className="hidden py-1.5 text-right font-medium sm:table-cell">Talk min</th></tr></thead>
          <tbody className="divide-y divide-card-border">
            {rows.slice(0, 8).map((row) => (
              <tr key={row.key}>
                <td className="py-1.5"><span className="flex min-w-0 items-center gap-2">{row.colour && <DeviceAvatar name={row.name} colour={row.colour} size={20} />}<span className="truncate text-text-primary">{row.name}</span></span></td>
                <td className="py-1.5 text-right tabular-nums">{row.calls}</td>
                <td className={cn("py-1.5 text-right tabular-nums", row.missed && "text-error-500")}>{row.missed}</td>
                <td className="py-1.5 text-right tabular-nums">{pct(row.answer_rate)}</td>
                <td className="hidden py-1.5 text-right tabular-nums sm:table-cell">{row.talk_minutes}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </SectionCard>
  );
}

function Outcomes({ data }: { data: CallStats }) {
  const total = data.outcomes.reduce((sum, o) => sum + o.count, 0);
  return (
    <SectionCard title="Outcomes" description="What calls were about (notes on the phone or in the admin)">
      {total === 0 ? <p className="py-6 text-center text-sm text-text-tertiary">No outcomes recorded yet.</p> : (
        <ul className="space-y-2">
          {data.outcomes.map((o) => (
            <li key={o.id} className="text-sm">
              <div className="flex justify-between"><span className="text-text-primary">{o.name}</span><span className="tabular-nums text-text-secondary">{o.count} · {Math.round((o.count / total) * 100)}%</span></div>
              <div className="mt-1 h-1.5 rounded-full bg-background-gray-secondary_alt" aria-hidden="true"><div className="h-full rounded-full" style={{ width: `${(o.count / total) * 100}%`, background: o.colour }} /></div>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}

function Cost({ data }: { data: CallStats }) {
  return (
    <SectionCard title="Estimated cost" description="Outgoing answered minutes × the carrier tariff (an estimate; the carrier bill decides)"
      actions={<Link href="/calls/tools/tariffs" className="text-xs font-medium text-primary-500 hover:underline">Tariffs</Link>}>
      {data.kpis.estimated_cost.length === 0 ? <EmptyState compact icon={<CoinsIcon />} title="No outgoing minutes" body="Answered outgoing calls appear here." /> : (
        <ul className="divide-y divide-card-border">
          {data.kpis.estimated_cost.map((row) => (
            <li key={row.carrier} className="flex justify-between py-2 text-sm">
              <span className="text-text-primary">{row.carrier}</span>
              <span className="tabular-nums text-text-secondary">{row.minutes} min · {row.amount ? `${row.currency} ${Number(row.amount).toLocaleString()}` : "no tariff set"}</span>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}
