"use client";

import Link from "next/link";
import { useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipContentProps } from "recharts";
import type { NameType, ValueType } from "recharts/types/component/DefaultTooltipContent";
import { formatInTimeZone } from "date-fns-tz";
import { usePageTitle } from "@/components/shell/trail";
import { useSession } from "@/components/shell/session-provider";
import { ButtonLink } from "@/components/tailgrids/core/button-link";
import { EmptyState } from "@/components/ui/empty-state";
import { CheckCircleIcon, ClockIcon, ErrorIcon, InboxIcon, MessageIcon, OutboxIcon, PlusIcon, SendIcon, WarningIcon } from "@/components/ui/icons";
import { Page, PageHeader } from "@/components/ui/page";
import { PageSkeleton, RequestState } from "@/components/ui/request-state";
import { SectionCard, StatCard } from "@/components/ui/section-card";
import { m } from "@/i18n";
import { compactNumber, dateTime, listTime, minutesLabel, timezone } from "@/lib/format";
import { errorMessage } from "@/services/api/client";
import type { SmsStats } from "@/services/api/types";
import { useCurrentDevice, useDeviceScope, useSmsStats } from "@/platforms/sms/api/queries";
import { DeviceAvatar, OnlineLabel } from "@/platforms/sms/components/device-badges";
import { setDeviceScope } from "@/platforms/sms/state";
import { cn } from "@/utils/cn";

const RANGES = [7, 30, 90] as const;
const SERIES = [
  { key: "received", name: "Received", colour: "var(--chart-received)" },
  { key: "sent", name: "Sent", colour: "var(--chart-sent)" },
] as const;
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const dayLabel = (iso: string) => formatInTimeZone(new Date(`${iso}T12:00:00Z`), timezone(), "d MMM");

export default function SmsDashboardPage() {
  usePageTitle({ page: "Dashboard", section: "SMS" });
  const [scope] = useDeviceScope();
  const current = useCurrentDevice();
  const { can } = useSession();
  const [days, setDays] = useState<(typeof RANGES)[number]>(30);
  const [sim, setSim] = useState<number | undefined>();
  const stats = useSmsStats(scope, days, sim);

  if (stats.isPending) return <Page wide><PageSkeleton /></Page>;
  if (stats.error && !stats.data) return <Page wide><RequestState loading={false} error={errorMessage(stats.error)} onRetry={() => stats.refetch()} /></Page>;
  const data = stats.data!;

  return (
    <Page wide key={scope}>
      <PageHeader eyebrow="Overview" title="SMS dashboard"
        description={scope === "all" ? "Every phone you can open, at a glance. Numbers only: no message text is read for these figures." : `${current?.name ?? "This phone"} at a glance.`}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {current && current.sims.length > 1 && (
              <select aria-label="SIM" value={sim ?? ""} onChange={(e) => setSim(e.target.value ? Number(e.target.value) : undefined)}
                className="h-9 rounded-lg border border-card-border bg-card-surface-area px-2 text-sm text-text-primary">
                <option value="">{m.sms.filters.allSims}</option>
                {current.sims.map((line) => <option key={line.id} value={line.id}>{line.label}</option>)}
              </select>
            )}
            <RangePicker value={days} onChange={setDays} />
          </div>
        } />
      {data.per_device.length === 0 ? (
        <SectionCard>
          <EmptyState icon={<MessageIcon />} title={m.sms.empty.noDevices.title} body={m.sms.empty.noDevices.body}
            action={can("sms.manage_devices") ? <ButtonLink href="/sms/devices/enroll"><PlusIcon size={16} />{m.sms.devices.enroll}</ButtonLink> : undefined} />
        </SectionCard>
      ) : (
        <div className={cn("space-y-4 sm:space-y-5", stats.isPlaceholderData && "opacity-70 transition-opacity")} data-sms-dashboard="">
          <Kpis data={data} />
          <div className="grid gap-4 sm:gap-5 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
            <TrafficChart data={data} days={days} />
            <TopSenders data={data} />
          </div>
          <div className="grid gap-4 sm:gap-5 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
            <Heatmap data={data} />
            <Failures data={data} />
          </div>
          <div className="grid gap-4 sm:gap-5 xl:grid-cols-2">
            <Latest data={data} />
            <Devices data={data} />
          </div>
        </div>
      )}
    </Page>
  );
}

function RangePicker({ value, onChange }: { value: number; onChange: (days: (typeof RANGES)[number]) => void }) {
  return (
    <div role="radiogroup" aria-label="Date range" className="inline-flex rounded-lg border border-card-border bg-card-surface-area p-0.5">
      {RANGES.map((range) => (
        <button key={range} type="button" role="radio" aria-checked={value === range} onClick={() => onChange(range)}
          className={cn("h-8 rounded-md px-3 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none",
            value === range ? "bg-primary-500 text-white" : "text-text-secondary hover:text-text-primary")}>
          {range} days
        </button>
      ))}
    </div>
  );
}

function Kpis({ data }: { data: SmsStats }) {
  const k = data.kpis;
  return (
    <dl className="grid grid-cols-2 gap-2 sm:gap-3 md:grid-cols-4 2xl:grid-cols-8">
      <StatCard label="Received" icon={<InboxIcon size={14} />} value={compactNumber(k.received)} hint={`Last ${data.range_days} days`} />
      <StatCard label="Sent" icon={<SendIcon size={14} />} value={compactNumber(k.sent)} hint={`Last ${data.range_days} days`} />
      <StatCard label="Unread" icon={<MessageIcon size={14} />} value={compactNumber(k.unread)} />
      <StatCard label="Awaiting reply > 1 h" icon={<ClockIcon size={14} />} value={k.awaiting_reply} tone={k.awaiting_reply ? "warning" : undefined}
        hint={k.awaiting_reply ? <Link href="/sms/awaiting" className="font-medium text-primary-500 hover:underline">Answer now</Link> : "Nobody waiting"} />
      <StatCard label="Median first response" icon={<ClockIcon size={14} />} value={minutesLabel(k.median_first_response_minutes)} />
      <StatCard label="Delivery success" icon={<CheckCircleIcon size={14} />} value={k.delivery_success_rate === null ? "—" : `${k.delivery_success_rate}%`} tone={k.delivery_success_rate !== null && k.delivery_success_rate < 90 ? "warning" : undefined} />
      <StatCard label="Failed" icon={<ErrorIcon size={14} />} value={k.failed} tone={k.failed ? "error" : undefined} />
      <StatCard label="In the outbox" icon={<OutboxIcon size={14} />} value={k.queued} hint={k.queued ? <Link href="/sms/outbox" className="font-medium text-primary-500 hover:underline">Open outbox</Link> : undefined} />
    </dl>
  );
}

function ChartTooltip({ active, payload, label }: TooltipContentProps<ValueType, NameType>) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-card-border bg-card-surface-area px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 font-medium text-text-primary">{dayLabel(String(label))}</p>
      {SERIES.map((series) => {
        const item = payload.find((entry) => entry.dataKey === series.key);
        return (
          <p key={series.key} className="flex items-center gap-2 text-text-secondary">
            <span className="size-2 rounded-full" style={{ background: series.colour }} aria-hidden="true" />
            {series.name}<span className="ml-auto pl-3 font-semibold tabular-nums text-text-primary">{item?.value ?? 0}</span>
          </p>
        );
      })}
    </div>
  );
}

function TrafficChart({ data, days }: { data: SmsStats; days: number }) {
  const [asTable, setAsTable] = useState(false);
  const totals = { received: data.series.reduce((s, d) => s + d.received, 0), sent: data.series.reduce((s, d) => s + d.sent, 0) };
  return (
    <SectionCard title="Received vs sent" description={`Messages per day, last ${days} days`}
      actions={<button type="button" onClick={() => setAsTable((v) => !v)} className="text-xs font-medium text-primary-500 hover:underline">{asTable ? "View chart" : "View as table"}</button>}>
      <ul className="mb-3 flex flex-wrap gap-4 text-xs text-text-secondary" aria-label="Legend">
        {SERIES.map((series) => (
          <li key={series.key} className="flex items-center gap-2">
            <span className="h-0.5 w-4 rounded-full" style={{ background: series.colour }} aria-hidden="true" />
            {series.name} <span className="font-semibold tabular-nums text-text-primary">{compactNumber(totals[series.key])}</span>
          </li>
        ))}
      </ul>
      {asTable ? (
        <div className="max-h-72 overflow-auto rounded-lg border border-card-border">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-card-surface-area text-left text-xs text-text-tertiary"><tr><th className="px-3 py-2 font-medium">Day</th><th className="px-3 py-2 text-right font-medium">Received</th><th className="px-3 py-2 text-right font-medium">Sent</th></tr></thead>
            <tbody className="divide-y divide-card-border">
              {[...data.series].reverse().map((row) => <tr key={row.date}><td className="px-3 py-1.5 text-text-secondary">{dayLabel(row.date)}</td><td className="px-3 py-1.5 text-right tabular-nums">{row.received}</td><td className="px-3 py-1.5 text-right tabular-nums">{row.sent}</td></tr>)}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="h-64 sm:h-72" role="img" aria-label={`Area chart: ${totals.received} received and ${totals.sent} sent in the last ${days} days`}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data.series} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
              <defs>
                {SERIES.map((series) => (
                  <linearGradient key={series.key} id={`sms-fill-${series.key}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={series.colour} stopOpacity={0.22} />
                    <stop offset="100%" stopColor={series.colour} stopOpacity={0} />
                  </linearGradient>
                ))}
              </defs>
              <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
              <XAxis dataKey="date" tickFormatter={dayLabel} tickLine={false} axisLine={false} minTickGap={24} tick={{ fill: "var(--text-tertiary)", fontSize: 11 }} />
              <YAxis allowDecimals={false} tickLine={false} axisLine={false} width={44} tick={{ fill: "var(--text-tertiary)", fontSize: 11 }} />
              <Tooltip content={ChartTooltip} cursor={{ stroke: "var(--text-tertiary)", strokeDasharray: "3 3" }} />
              {SERIES.map((series) => (
                <Area key={series.key} type="monotone" dataKey={series.key} name={series.name} stroke={series.colour} strokeWidth={2} fill={`url(#sms-fill-${series.key})`}
                  activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--card-surface-area)" }} isAnimationActive={false} />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </SectionCard>
  );
}

function TopSenders({ data }: { data: SmsStats }) {
  const max = Math.max(1, ...data.top_senders.map((s) => s.count));
  return (
    <SectionCard title="Top senders" description={`Who wrote most, last ${data.range_days} days`}>
      {data.top_senders.length === 0 ? <p className="py-6 text-center text-sm text-text-tertiary">No messages received in this period.</p> : (
        <ol className="space-y-2.5">
          {data.top_senders.map((sender) => (
            <li key={`${sender.device_id}-${sender.address}`} className="min-w-0">
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span className="min-w-0 truncate text-text-primary" title={sender.display}>{sender.name || sender.display}{sender.name && <span className="text-text-tertiary"> · {sender.display}</span>}</span>
                <span className="shrink-0 tabular-nums text-text-secondary">{sender.count}</span>
              </div>
              <div className="mt-1 h-1.5 rounded-full bg-background-gray-secondary_alt" aria-hidden="true"><div className="h-full rounded-full bg-[var(--chart-received)]" style={{ width: `${(sender.count / max) * 100}%` }} /></div>
            </li>
          ))}
        </ol>
      )}
    </SectionCard>
  );
}

function Heatmap({ data }: { data: SmsStats }) {
  const max = Math.max(1, ...data.heatmap.flat());
  return (
    <SectionCard title="Busiest hours" description="Messages received by weekday and hour (your time zone)">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] border-separate border-spacing-0.5 text-[10px]" aria-label="Messages received by weekday and hour">
          <thead><tr><th className="w-8" />{Array.from({ length: 24 }, (_, h) => <th key={h} scope="col" className="font-normal text-text-tertiary">{h % 3 === 0 ? h : ""}</th>)}</tr></thead>
          <tbody>
            {data.heatmap.map((row, day) => (
              <tr key={DAYS[day]}>
                <th scope="row" className="pr-1 text-left font-medium text-text-tertiary">{DAYS[day]}</th>
                {row.map((value, hour) => (
                  <td key={hour} title={`${DAYS[day]} ${hour}:00 — ${value} received`} className="h-5 rounded-sm"
                    style={{ background: value ? `color-mix(in oklab, var(--chart-received) ${Math.round(15 + (value / max) * 85)}%, transparent)` : "var(--chart-grid)" }}>
                    <span className="sr-only">{value}</span>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.per_sim.length > 1 && (
        <div className="mt-4">
          <h3 className="mb-2 text-xs font-semibold tracking-wider text-text-tertiary uppercase">Per SIM</h3>
          <ul className="grid gap-2 sm:grid-cols-2">
            {data.per_sim.map((line) => <li key={line.sim_id ?? "none"} className="flex justify-between rounded-lg border border-card-border px-3 py-2 text-sm"><span className="text-text-primary">{line.label}</span><span className="tabular-nums text-text-secondary">{line.received} in · {line.sent} out</span></li>)}
          </ul>
        </div>
      )}
    </SectionCard>
  );
}

function Failures({ data }: { data: SmsStats }) {
  return (
    <SectionCard title="Why messages failed" description={`Last ${data.range_days} days`}>
      {data.failure_reasons.length === 0 ? <EmptyState compact icon={<CheckCircleIcon />} title="No failures" body="Every message from the admin was sent." /> : (
        <ul className="divide-y divide-card-border">
          {data.failure_reasons.map((reason) => (
            <li key={`${reason.status}-${reason.code}`} className="flex items-start justify-between gap-3 py-2.5 text-sm">
              <span className="text-text-primary">{reason.reason}</span><span className="shrink-0 font-semibold tabular-nums text-error-500">{reason.count}</span>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}

function Latest({ data }: { data: SmsStats }) {
  return (
    <SectionCard title="Latest conversations" actions={<Link href="/sms/inbox" className="text-sm font-medium text-primary-500 hover:underline">Open inbox</Link>}>
      <ul className="divide-y divide-card-border">
        {data.latest.map((item) => (
          <li key={item.id}>
            <Link href={`/sms/inbox?c=${item.id}`} className="flex min-w-0 items-center gap-3 rounded-lg px-1 py-2.5 hover:bg-background-gray-secondary_alt/40 focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none">
              <span className="min-w-0 flex-1">
                <span className={cn("block truncate text-sm", item.unread ? "font-semibold text-text-primary" : "text-text-primary")}>{item.title}</span>
                <span className="block truncate text-xs text-text-tertiary">{item.device} · {item.snippet}</span>
              </span>
              <span className="shrink-0 text-xs text-text-tertiary tabular-nums">{listTime(item.last_message_at)}</span>
            </Link>
          </li>
        ))}
      </ul>
    </SectionCard>
  );
}

function Devices({ data }: { data: SmsStats }) {
  const attention = new Map(data.attention.map((item) => [item.id, item.alerts]));
  return (
    <SectionCard title="Phones" description="Volume and health per phone" actions={<Link href="/sms/devices" className="text-sm font-medium text-primary-500 hover:underline">Manage</Link>}>
      <ul className="divide-y divide-card-border">
        {data.per_device.map((device) => (
          <li key={device.id} className="flex min-w-0 items-center gap-3 py-2.5">
            <DeviceAvatar name={device.name} colour={device.colour} online={device.online} size={32} />
            <div className="min-w-0 flex-1">
              <Link href={`/sms/devices/${device.id}`} className="block truncate text-sm font-medium text-text-primary hover:underline">{device.name}</Link>
              <p className="truncate text-xs text-text-tertiary"><OnlineLabel online={device.online} lastSeen={device.last_seen_at} /> · {device.received} in · {device.sent} out</p>
              {attention.get(device.id)?.length ? (
                <p className="mt-0.5 flex items-center gap-1 text-xs text-warning-700 dark:text-warning-300"><WarningIcon size={12} />{attention.get(device.id)!.map((a) => a.label).join(" · ")}</p>
              ) : null}
            </div>
            <button type="button" onClick={() => setDeviceScope(device.id)} className="shrink-0 text-xs font-medium text-primary-500 hover:underline">View</button>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-text-tertiary">Updated {dateTime(data.generated_at)}</p>
    </SectionCard>
  );
}
