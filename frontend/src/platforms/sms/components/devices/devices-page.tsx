"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useSession } from "@/components/shell/session-provider";
import { usePageTitle } from "@/components/shell/trail";
import { Button } from "@/components/tailgrids/core/button";
import { EmptyState } from "@/components/ui/empty-state";
import { CheckIcon, InboxIcon, PlusIcon, SmartphoneIcon, WarningIcon } from "@/components/ui/icons";
import { Page, PageHeader } from "@/components/ui/page";
import { PageSkeleton, RequestState } from "@/components/ui/request-state";
import { cardClass } from "@/components/ui/section-card";
import { Chip } from "@/components/ui/status-pill";
import { m } from "@/i18n";
import { errorMessage } from "@/services/api/client";
import type { Device } from "@/services/api/types";
import { cn } from "@/utils/cn";
import { useDevices } from "../../api/queries";
import { setDeviceScope } from "../../state";
import { DeviceAvatar, DeviceStatusPill, OnlineLabel } from "../device-badges";
import { EnrollDialog } from "./enroll-dialog";

export function DevicesPage({ enroll = false }: { enroll?: boolean }) {
  usePageTitle({ page: m.sms.devices.title, section: "Devices" });
  const { can } = useSession();
  const router = useRouter();
  const [showRemoved, setShowRemoved] = useState(false);
  const devices = useDevices(showRemoved);
  const [open, setOpen] = useState(enroll);
  const canEnroll = can("sms.manage_devices");
  return (
    <Page wide>
      <PageHeader title={m.sms.devices.title} description="Company phones whose text messages are copied here. Android only: iPhones do not let any app read or send SMS."
        actions={<>
          <label className="flex items-center gap-2 text-sm text-text-secondary"><input type="checkbox" checked={showRemoved} onChange={(e) => setShowRemoved(e.target.checked)} className="size-4 rounded" />Show removed</label>
          {canEnroll && <Button onPress={() => setOpen(true)}><PlusIcon size={16} />{m.sms.devices.enroll}</Button>}
        </>} />
      {devices.isPending ? <PageSkeleton /> : devices.error ? <RequestState loading={false} error={errorMessage(devices.error)} onRetry={() => devices.refetch()} /> : devices.data!.length === 0 ? (
        <div className={cardClass()}>
          <EmptyState icon={<SmartphoneIcon />} title={m.sms.empty.noDevices.title} body={m.sms.empty.noDevices.body}
            action={canEnroll ? <Button onPress={() => setOpen(true)}><PlusIcon size={16} />{m.sms.devices.enroll}</Button> : undefined} />
        </div>
      ) : (
        <ul className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
          {devices.data!.map((device) => <DeviceCard key={device.id} device={device} onOpenInbox={() => { setDeviceScope(device.id); router.push("/sms/inbox"); }} />)}
        </ul>
      )}
      <EnrollDialog isOpen={open} onOpenChange={(value) => { setOpen(value); if (!value && enroll) router.replace("/sms/devices"); }} />
    </Page>
  );
}

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="min-w-0"><dt className="text-[11px] text-text-tertiary">{label}</dt><dd className="truncate text-sm text-text-primary">{children}</dd></div>;
}

function DeviceCard({ device, onOpenInbox }: { device: Device; onOpenInbox: () => void }) {
  const attention = device.attention.length > 0;
  return (
    <li className={cn(cardClass({ interactive: true }), "flex flex-col gap-4", attention && "border-warning-500/50")} data-device-card={device.code}>
      <div className="flex min-w-0 items-start gap-3">
        <DeviceAvatar name={device.name} colour={device.office.colour} online={device.online} size={40} />
        <div className="min-w-0 flex-1">
          <Link href={`/sms/devices/${device.id}`} className="block truncate font-semibold text-text-primary hover:text-primary-500 hover:underline">{device.name}</Link>
          <p className="truncate text-sm text-text-tertiary"><span className="font-mono">{device.code}</span> · {device.office.name}{device.assigned_to ? ` · ${device.assigned_to.display_name}` : ""}</p>
        </div>
        <DeviceStatusPill status={device.status} online={device.online} />
      </div>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3">
        <Fact label="Seen"><OnlineLabel online={device.online} lastSeen={device.last_seen_at} /></Fact>
        <Fact label="Default SMS app">{device.is_default_sms_app || device.is_simulated ? <span className="inline-flex items-center gap-1 text-success-600 dark:text-success-400"><CheckIcon size={14} />Yes</span> : <span className="text-warning-600 dark:text-warning-400">No</span>}</Fact>
        <Fact label="Battery">{device.battery === null ? "—" : `${device.battery}%${device.charging ? " ⚡" : ""}`}</Fact>
        <Fact label="App">{device.app_version || "—"}</Fact>
        <Fact label="Upload backlog">{device.pending_outbox}</Fact>
        <Fact label="Unread">{device.unread}</Fact>
      </dl>
      {attention && (
        <ul className="flex flex-wrap gap-1.5">{device.attention.map((alert) => <li key={alert.code}><Chip className="gap-1 bg-warning-500/10 text-warning-700 dark:text-warning-300"><WarningIcon size={12} />{alert.label}</Chip></li>)}</ul>
      )}
      {device.is_simulated && <Chip className="self-start">Simulated phone (demo)</Chip>}
      <div className="mt-auto flex flex-wrap gap-2 border-t border-card-border pt-3">
        {device.status !== "revoked" && <Button size="sm" appearance="outline" onPress={onOpenInbox}><InboxIcon size={15} />Open inbox</Button>}
        <Link href={`/sms/devices/${device.id}`} className="ml-auto inline-flex h-8 items-center rounded-lg px-3 text-sm font-medium text-text-secondary hover:bg-background-gray-secondary_alt hover:text-text-primary">Manage</Link>
      </div>
    </li>
  );
}
