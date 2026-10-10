"use client";

import Link from "next/link";
import { useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipContentProps } from "recharts";
import type { NameType, ValueType } from "recharts/types/component/DefaultTooltipContent";
import { usePageTitle } from "@/components/shell/trail";
import { ButtonLink } from "@/components/tailgrids/core/button-link";
import { EmptyState } from "@/components/ui/empty-state";
import { ClockIcon, InboxIcon, PlusIcon, SendIcon, WarningIcon, MailIcon, ChartIcon } from "@/components/ui/icons";
import { Page, PageHeader } from "@/components/ui/page";
import { PageSkeleton, RequestState } from "@/components/ui/request-state";
import { SectionCard, StatCard } from "@/components/ui/section-card";
import { compactNumber, dateTime, minutesLabel } from "@/lib/format";
import { formatInTimeZone } from "date-fns-tz";
import { timezone } from "@/lib/format";
import { errorMessage } from "@/services/api/client";
import type { Stats } from "@/services/api/types";
import { useMailboxScope, useStats } from "@/platforms/gmail/api/queries";
import { MailboxAvatar, MailboxStatus, ProviderBadge } from "@/platforms/gmail/components/mailbox-badges";
import { setMailboxScope } from "@/platforms/gmail/state";
import { cn } from "@/utils/cn";

const RANGES = [7, 30, 90] as const;
const SERIES = [
  { key: "received", name: "Received", colour: "var(--chart-received)" },
  { key: "sent", name: "Sent", colour: "var(--chart-sent)" },
] as const;

const dayLabel = (iso: string) => formatInTimeZone(new Date(`${iso}T12:00:00Z`), timezone(), "d MMM");

export default function DashboardPage() {
  usePageTitle({ page: "Dashboard", section: "Gmail" });
  const [scope] = useMailboxScope();
  const [days, setDays] = useState<(typeof RANGES)[number]>(30);
  const stats = useStats(scope, days);

  if (stats.isPending) return <Page wide><PageSkeleton /></Page>;
  if (stats.error && !stats.data) return <Page wide><RequestState loading={false} error={errorMessage(stats.error)} onRetry={() => stats.refetch()} /></Page>;
  const data = stats.data!;

  return (
    <Page wide>
      <PageHeader
        eyebrow="Overview"
        title="Mail dashboard"
        description={scope === "all" ? "Every mailbox you can open, at a glance." : "The selected mailbox at a glance."}
        actions={<RangePicker value={days} onChange={setDays} />}
      />
      {data.mailboxes.length === 0 ? (
        <SectionCard>
          <EmptyState icon={<MailIcon />} title="No mailboxes yet" body="Connect your first office in under a minute. Mail and statistics appear as soon as it syncs."
            action={<ButtonLink href="/gmail/mailboxes/new"><PlusIcon size={16} />Add mailbox</ButtonLink>} />
        </SectionCard>
      ) : (
        <div className={cn("space-y-4 sm:space-y-5", stats.isPlaceholderData && "opacity-70 transition-opacity")}>
          <Kpis data={data} />
          <div className="grid gap-4 sm:gap-5 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
            <TrafficChart data={data} days={days} />
            <TopSenders data={data} />
          </div>
          <MailboxTable data={data} />
          <Unanswered data={data} />
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

function Kpis({ data }: { data: Stats }) {
  const k = data.kpis;
  return (
    <dl className="grid grid-cols-2 gap-2 sm:gap-3 md:grid-cols-3 xl:grid-cols-5">
      <StatCard label="Unread" icon={<InboxIcon size={14} />} value={compactNumber(k.unread)} hint="Inbox, all selected mailboxes" />
      <StatCard label="Received today" icon={<MailIcon size={14} />} value={compactNumber(k.received_today)} />
      <StatCard label="Sent today" icon={<SendIcon size={14} />} value={compactNumber(k.sent_today)} />
      <StatCard label="Avg first response" icon={<ClockIcon size={14} />} value={minutesLabel(k.avg_first_response_minutes)} hint={`Last ${data.range_days} days`} />
      <StatCard label="Need reconnect" icon={<WarningIcon size={14} />} value={k.needs_reconnect} tone={k.needs_reconnect ? "warning" : undefined}
        hint={k.needs_reconnect ? <Link href="/gmail/mailboxes" className="font-medium text-primary-500 hover:underline">Fix now</Link> : "All connections healthy"} className="col-span-2 md:col-span-1" />
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

function TrafficChart({ data, days }: { data: Stats; days: number }) {
  const [asTable, setAsTable] = useState(false);
  const totals = { received: data.series.reduce((s, d) => s + d.received, 0), sent: data.series.reduce((s, d) => s + d.sent, 0) };
  return (
    <SectionCard
      title="Received vs sent"
      description={`Messages per day, last ${days} days`}
      actions={<button type="button" onClick={() => setAsTable((v) => !v)} className="text-xs font-medium text-primary-500 hover:underline">{asTable ? "View chart" : "View as table"}</button>}
    >
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
              {[...data.series].reverse().map((row) => (
                <tr key={row.date}><td className="px-3 py-1.5 text-text-secondary">{dayLabel(row.date)}</td><td className="px-3 py-1.5 text-right tabular-nums">{row.received}</td><td className="px-3 py-1.5 text-right tabular-nums">{row.sent}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="h-64 sm:h-72" role="img" aria-label={`Area chart: ${totals.received} received and ${totals.sent} sent in the last ${days} days`}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data.series} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
              <defs>
                {SERIES.map((series) => (
                  <linearGradient key={series.key} id={`fill-${series.key}`} x1="0" y1="0" x2="0" y2="1">
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
                <Area key={series.key} type="monotone" dataKey={series.key} name={series.name} stroke={series.colour} strokeWidth={2} fill={`url(#fill-${series.key})`}
                  activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--card-surface-area)" }} isAnimationActive={false} />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </SectionCard>
  );
}

function TopSenders({ data }: { data: Stats }) {
  const max = Math.max(1, ...data.top_senders.map((s) => s.count));
  return (
    <SectionCard title="Top senders" description={`Last ${data.range_days} days`}>
      {data.top_senders.length === 0 ? <p className="py-6 text-center text-sm text-text-tertiary">No mail received in this period.</p> : (
        <ol className="space-y-2.5">
          {data.top_senders.slice(0, 8).map((sender) => (
            <li key={sender.email} className="min-w-0">
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <Link href={`/gmail/search?q=${encodeURIComponent(`from:${sender.email}`)}`} className="min-w-0 truncate text-text-primary hover:text-primary-500" title={sender.email}>{sender.name || sender.email}</Link>
                <span className="shrink-0 tabular-nums text-text-secondary">{sender.count}</span>
              </div>
              <div className="mt-1 h-1.5 rounded-full bg-background-gray-secondary_alt" aria-hidden="true">
                <div className="h-full rounded-full bg-[var(--chart-received)]" style={{ width: `${(sender.count / max) * 100}%` }} />
              </div>
            </li>
          ))}
        </ol>
      )}
    </SectionCard>
  );
}

function MailboxTable({ data }: { data: Stats }) {
  return (
    <SectionCard title="Mailboxes" description="Status and activity per office" padding="none" className="overflow-hidden" bodyClassName="overflow-x-auto"
      actions={<Link href="/gmail/mailboxes" className="text-sm font-medium text-primary-500 hover:underline">Manage</Link>}>
      <table className="w-full min-w-[640px] text-sm">
        <thead className="border-y border-card-border bg-background-gray-secondary_alt/40 text-left text-xs text-text-tertiary">
          <tr>
            <th className="px-4 py-2.5 font-medium">Mailbox</th><th className="px-4 py-2.5 font-medium">Status</th>
            <th className="px-4 py-2.5 text-right font-medium">Unread</th><th className="px-4 py-2.5 font-medium">Last sync</th>
            <th className="px-4 py-2.5 font-medium">Last activity</th><th className="px-4 py-2.5"><span className="sr-only">Actions</span></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-card-border">
          {data.mailboxes.map((box) => (
            <tr key={box.id} className="hover:bg-background-gray-secondary_alt/30">
              <td className="px-4 py-3">
                <div className="flex min-w-0 items-center gap-3">
                  <MailboxAvatar name={box.name} colour={box.colour} size={30} />
                  <div className="min-w-0">
                    <p className="truncate font-medium text-text-primary">{box.office}</p>
                    <p className="flex items-center gap-1.5 truncate text-xs text-text-tertiary">{box.email} <ProviderBadge provider={box.provider} /></p>
                  </div>
                </div>
              </td>
              <td className="px-4 py-3"><MailboxStatus status={box.status} progress={box.sync_progress} /></td>
              <td className="px-4 py-3 text-right font-semibold tabular-nums">{box.unread}</td>
              <td className="px-4 py-3 text-text-secondary">{box.last_synced_at ? dateTime(box.last_synced_at) : "—"}</td>
              <td className="px-4 py-3 text-text-secondary">{box.last_activity_at ? dateTime(box.last_activity_at) : "—"}</td>
              <td className="px-4 py-3 text-right">
                <Link href="/gmail/inbox" onClick={() => setMailboxScope(box.id)} className="text-sm font-medium text-primary-500 hover:underline">Open inbox</Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </SectionCard>
  );
}

function Unanswered({ data }: { data: Stats }) {
  return (
    <SectionCard title="Waiting for a reply" description="Inbox conversations with no answer for more than 24 hours">
      {data.unanswered.length === 0 ? (
        <EmptyState compact icon={<ChartIcon />} title="Everyone has an answer" body="No conversation has been waiting longer than a day." />
      ) : (
        <ul className="divide-y divide-card-border">
          {data.unanswered.map((item) => (
            <li key={item.id}>
              <Link href={`/gmail/all?thread=${item.id}`} onClick={() => setMailboxScope("all")}
                className="flex min-w-0 items-center gap-3 rounded-lg px-1 py-2.5 hover:bg-background-gray-secondary_alt/40 focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none">
                <span className="size-2 shrink-0 rounded-full" style={{ background: item.colour }} aria-hidden="true" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-text-primary">{item.subject || "(no subject)"}</span>
                  <span className="block truncate text-xs text-text-tertiary">{item.from?.name || item.from?.email} · {item.mailbox}</span>
                </span>
                <span className={cn("shrink-0 text-xs font-medium tabular-nums", item.waiting_hours >= 72 ? "text-error-500" : "text-warning-600 dark:text-warning-400")}>
                  {item.waiting_hours >= 48 ? `${Math.floor(item.waiting_hours / 24)} d` : `${Math.round(item.waiting_hours)} h`}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}
