"use client";

import { useEffect, useState } from "react";
import { usePageTitle } from "@/components/shell/trail";
import { EmptyState } from "@/components/ui/empty-state";
import { LiveIcon, PhoneIcon } from "@/components/ui/icons";
import { Page, PageHeader } from "@/components/ui/page";
import { PageSkeleton, RequestState } from "@/components/ui/request-state";
import { SectionCard, StatCard } from "@/components/ui/section-card";
import { StatusPill, type Tone } from "@/components/ui/status-pill";
import { m } from "@/i18n";
import { ago } from "@/lib/format";
import { errorMessage } from "@/services/api/client";
import { useLive } from "@/platforms/calls/api/queries";
import { DeviceAvatar } from "@/platforms/sms/components/device-badges";

const TONE: Record<string, Tone> = { idle: "neutral", ringing: "warning", active: "success", held: "info", offline: "neutral" };

function useNow(interval = 1000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), interval);
    return () => window.clearInterval(timer);
  }, [interval]);
  return now;
}

function clock(seconds: number) {
  const s = Math.max(0, Math.floor(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export default function LivePage() {
  usePageTitle({ page: "Live", section: "Calls" });
  const live = useLive();
  const now = useNow();
  if (live.isPending) return <Page wide><PageSkeleton /></Page>;
  if (live.error && !live.data) return <Page wide><RequestState loading={false} error={errorMessage(live.error)} onRetry={() => live.refetch()} /></Page>;
  const data = live.data!;
  // The server clock may differ from this browser's: time on a call is measured against the server time of the poll.
  const skew = Date.parse(data.server_time) - Date.parse(new Date(live.dataUpdatedAt).toISOString());
  return (
    <Page wide>
      <PageHeader eyebrow="Overview" title="Live" description="What every phone is doing now. Refreshes every few seconds while this tab is open." />
      <dl className="mb-5 grid grid-cols-2 gap-2 sm:gap-3 md:grid-cols-5">
        <StatCard label="On a call" value={data.totals.on_call} tone={data.totals.on_call ? "success" : undefined} />
        <StatCard label="Ringing" value={data.totals.ringing} tone={data.totals.ringing ? "warning" : undefined} />
        <StatCard label="Offline" value={data.totals.offline} />
        <StatCard label="Calls today" value={data.totals.calls_today} />
        <StatCard label="Missed today" value={data.totals.missed_today} tone={data.totals.missed_today ? "error" : undefined} />
      </dl>
      {data.phones.length === 0 ? <SectionCard><EmptyState icon={<PhoneIcon />} title={m.calls.empty.noDevices.title} body={m.calls.empty.noDevices.body} /></SectionCard> : (
        <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3" aria-label="Phones" data-live-board="">
          {data.phones.map((phone) => (
            <li key={phone.id} data-live-phone={phone.name} data-state={phone.state}>
              <SectionCard padding="sm" className={phone.state === "ringing" ? "border-warning-400" : phone.state === "active" ? "border-success-400" : undefined}>
                <div className="flex items-center gap-3">
                  <DeviceAvatar name={phone.name} colour={phone.colour} online={phone.state !== "offline"} size={36} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium text-text-primary">{phone.name}</p>
                    <p className="truncate text-xs text-text-tertiary">{phone.holder || phone.office} · {phone.code}</p>
                  </div>
                  <StatusPill tone={TONE[phone.state]} pulse={phone.state === "ringing"}>
                    {m.calls.state[phone.state]}{phone.since && (phone.state === "active" || phone.state === "held") ? ` ${clock((now + skew - Date.parse(phone.since)) / 1000)}` : ""}
                  </StatusPill>
                </div>
                <p className="mt-2 flex justify-between text-xs text-text-tertiary">
                  <span>{phone.today_calls} calls today{phone.today_missed ? ` · ${phone.today_missed} missed` : ""}</span>
                  <span>{phone.state === "offline" && phone.last_seen_at ? `Last seen ${ago(phone.last_seen_at)}` : <LiveIcon size={14} aria-hidden="true" />}</span>
                </p>
              </SectionCard>
            </li>
          ))}
        </ul>
      )}
    </Page>
  );
}
