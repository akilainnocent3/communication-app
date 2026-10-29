"use client";

import Link from "next/link";
import { useState } from "react";
import { usePageTitle } from "@/components/shell/trail";
import { useSession } from "@/components/shell/session-provider";
import { Button } from "@/components/tailgrids/core/button";
import { EmptyState } from "@/components/ui/empty-state";
import { PlusIcon, SmartphoneIcon, WarningIcon } from "@/components/ui/icons";
import { Page, PageHeader } from "@/components/ui/page";
import { RequestState } from "@/components/ui/request-state";
import { SectionCard } from "@/components/ui/section-card";
import { StatusPill } from "@/components/ui/status-pill";
import { m } from "@/i18n";
import { errorMessage } from "@/services/api/client";
import type { CallDevice } from "@/services/api/types";
import { useEnableCalls } from "@/platforms/calls/api/actions";
import { useCallDevices } from "@/platforms/calls/api/queries";
import { CallsEnrollDialog } from "@/platforms/calls/components/enroll-dialog";
import { DeviceAvatar, OnlineLabel } from "@/platforms/sms/components/device-badges";

export default function CallsDevicesPage() {
  usePageTitle({ page: "Phones", section: "Calls" });
  const { can } = useSession();
  const manage = can("calls.manage_settings");
  const phones = useCallDevices();
  const enable = useEnableCalls();
  const [enrolling, setEnrolling] = useState(false);
  return (
    <Page wide>
      <PageHeader eyebrow="Devices" title="Calls phones" description="Phones running OCM Phone, the company's Phone app. It is a separate app from OCM Messages, with its own enrollment."
        actions={manage ? <Button onPress={() => setEnrolling(true)}><PlusIcon size={16} />{m.calls.enroll.button}</Button> : undefined} />
      {phones.isPending ? <RequestState loading variant="table" onRetry={() => phones.refetch()} /> : phones.error ? (
        <RequestState loading={false} error={errorMessage(phones.error)} onRetry={() => phones.refetch()} />
      ) : (phones.data ?? []).length === 0 ? (
        <SectionCard><EmptyState icon={<SmartphoneIcon />} title={m.calls.empty.noDevices.title} body={m.calls.empty.noDevices.body}
          action={manage ? <Button onPress={() => setEnrolling(true)}>{m.calls.enroll.button}</Button> : undefined} /></SectionCard>
      ) : (
        <ul className="grid gap-3 lg:grid-cols-2" data-calls-devices="">
          {phones.data!.map((device) => (
            <PhoneCard key={device.id} device={device} action={manage && device.app === "calls" && device.status === "active" ? (
              <Button size="sm" appearance="outline" onPress={() => enable.mutateAsync({ id: device.id, enabled: !device.calls_enabled })}>{device.calls_enabled ? "Switch Calls off" : "Switch Calls on"}</Button>
            ) : undefined} />
          ))}
        </ul>
      )}
      {manage && <CallsEnrollDialog isOpen={enrolling} onOpenChange={setEnrolling} />}
    </Page>
  );
}

function PhoneCard({ device, action }: { device: CallDevice; action?: React.ReactNode }) {
  const backfill = device.calls_backfill as { phase?: string; done?: number; total?: number };
  const attention = device.attention as unknown as { code: string; label: string }[];
  const companion = device.companion as { id: string; name: string; code: string } | null;
  return (
    <li data-calls-device={device.name}>
      <SectionCard padding="sm">
        <div className="flex items-center gap-3">
          <DeviceAvatar name={device.name} colour={device.colour} online={device.online} size={36} />
          <div className="min-w-0 flex-1">
            <p className="truncate font-medium text-text-primary">{device.name}</p>
            <p className="truncate text-xs text-text-tertiary">{device.code} · {device.office}{device.holder ? ` · ${device.holder}` : ""}</p>
            {companion && <p className="truncate text-xs text-text-tertiary" data-companion="">Same handset as OCM Messages · {companion.name} ({companion.code})</p>}
          </div>
          {device.calls_enabled ? <StatusPill tone={device.is_default_dialer ? "success" : "warning"}>{device.is_default_dialer ? "Default Phone app" : "Not the Phone app"}</StatusPill>
            : <StatusPill tone="neutral">Calls off</StatusPill>}
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
          {companion && <Link href={`/sms/devices/${companion.id}`} className="inline-flex h-8 items-center rounded-lg border border-card-border px-3 text-sm font-medium hover:bg-background-gray-secondary_alt">SMS phone</Link>}
          <Link href={`/calls/log/all`} className="inline-flex h-8 items-center rounded-lg border border-card-border px-3 text-sm font-medium hover:bg-background-gray-secondary_alt">Calls</Link>
          {action}
        </div>
      </SectionCard>
    </li>
  );
}
