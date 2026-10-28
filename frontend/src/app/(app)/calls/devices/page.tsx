"use client";

import Link from "next/link";
import { usePageTitle } from "@/components/shell/trail";
import { useSession } from "@/components/shell/session-provider";
import { Button } from "@/components/tailgrids/core/button";
import { EmptyState } from "@/components/ui/empty-state";
import { SmartphoneIcon, WarningIcon } from "@/components/ui/icons";
import { Page, PageHeader } from "@/components/ui/page";
import { RequestState } from "@/components/ui/request-state";
import { SectionCard } from "@/components/ui/section-card";
import { StatusPill } from "@/components/ui/status-pill";
import { m } from "@/i18n";
import { errorMessage } from "@/services/api/client";
import type { CallDevice } from "@/services/api/types";
import { useEnableCalls } from "@/platforms/calls/api/actions";
import { useCallDevices } from "@/platforms/calls/api/queries";
import { DeviceAvatar, OnlineLabel } from "@/platforms/sms/components/device-badges";

export default function CallsDevicesPage() {
  usePageTitle({ page: "Phones", section: "Calls" });
  const { can } = useSession();
  const manage = can("calls.manage_settings");
  const phones = useCallDevices();
  const candidates = useCallDevices(true, manage);
  const enable = useEnableCalls();
  return (
    <Page wide>
      <PageHeader eyebrow="Devices" title="Calls phones" description="Phones where OCM is also the default Phone app. Enrollment, SIMs and access are on each phone's page in SMS → Phones." />
      {phones.isPending ? <RequestState loading variant="table" onRetry={() => phones.refetch()} /> : phones.error ? (
        <RequestState loading={false} error={errorMessage(phones.error)} onRetry={() => phones.refetch()} />
      ) : (phones.data ?? []).length === 0 ? (
        <SectionCard><EmptyState icon={<SmartphoneIcon />} title={m.calls.empty.noDevices.title} body={m.calls.empty.noDevices.body} /></SectionCard>
      ) : (
        <ul className="grid gap-3 lg:grid-cols-2" data-calls-devices="">
          {phones.data!.map((device) => <PhoneCard key={device.id} device={device} action={manage ? <Button size="sm" appearance="outline" onPress={() => enable.mutateAsync({ id: device.id, enabled: false })}>Switch Calls off</Button> : undefined} />)}
        </ul>
      )}
      {manage && (candidates.data ?? []).length > 0 && (
        <SectionCard className="mt-5" title="Enable Calls on a phone" description="The phone asks its holder to make OCM the default Phone app, then copies its call history (within the phone's backfill window).">
          <ul className="divide-y divide-card-border">
            {candidates.data!.map((device) => (
              <li key={device.id} className="flex items-center gap-3 py-2.5" data-candidate={device.name}>
                <DeviceAvatar name={device.name} colour={device.colour} online={device.online} />
                <span className="min-w-0 flex-1"><span className="block truncate text-sm font-medium">{device.name}</span><span className="block text-xs text-text-tertiary">{device.code} · {device.office}</span></span>
                <Button size="sm" onPress={() => enable.mutateAsync({ id: device.id, enabled: true })}>Enable Calls</Button>
              </li>
            ))}
          </ul>
        </SectionCard>
      )}
    </Page>
  );
}

function PhoneCard({ device, action }: { device: CallDevice; action?: React.ReactNode }) {
  const backfill = device.calls_backfill as { phase?: string; done?: number; total?: number };
  const attention = device.attention as unknown as { code: string; label: string }[];
  return (
    <li data-calls-device={device.name}>
      <SectionCard padding="sm">
        <div className="flex items-center gap-3">
          <DeviceAvatar name={device.name} colour={device.colour} online={device.online} size={36} />
          <div className="min-w-0 flex-1">
            <p className="truncate font-medium text-text-primary">{device.name}</p>
            <p className="truncate text-xs text-text-tertiary">{device.code} · {device.office}{device.holder ? ` · ${device.holder}` : ""}</p>
          </div>
          <StatusPill tone={device.is_default_dialer ? "success" : "warning"}>{device.is_default_dialer ? "Default Phone app" : "Not the Phone app"}</StatusPill>
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-text-tertiary">
          <OnlineLabel online={device.online} lastSeen={device.last_seen_at} />
          <span>{m.calls.state[device.call_state || "idle"]}</span>
          {backfill.phase === "running" && <span>Copying call history {backfill.done}/{backfill.total}</span>}
          {device.full_screen_intent_allowed === false && <span className="text-warning-600">Incoming-call screen not allowed</span>}
        </div>
        {attention.length > 0 && (
          <ul className="mt-2 space-y-1">{attention.map((alert) => <li key={alert.code} className="flex items-center gap-1.5 text-xs text-warning-600"><WarningIcon size={14} />{alert.label}</li>)}</ul>
        )}
        <div className="mt-3 flex flex-wrap gap-2">
          <Link href={`/sms/devices/${device.id}`} className="inline-flex h-8 items-center rounded-lg border border-card-border px-3 text-sm font-medium hover:bg-background-gray-secondary_alt">Phone page</Link>
          <Link href={`/calls/log/all`} className="inline-flex h-8 items-center rounded-lg border border-card-border px-3 text-sm font-medium hover:bg-background-gray-secondary_alt">Calls</Link>
          {action}
        </div>
      </SectionCard>
    </li>
  );
}
