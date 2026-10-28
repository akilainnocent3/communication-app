"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { ME_KEY, useSession } from "@/components/shell/session-provider";
import { usePageTitle } from "@/components/shell/trail";
import { Button } from "@/components/tailgrids/core/button";
import { ButtonLink } from "@/components/tailgrids/core/button-link";
import { Dialog, DialogHeader, DialogTitle } from "@/components/tailgrids/core/dialog";
import { Progress } from "@/components/tailgrids/core/progress";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Field } from "@/components/ui/field";
import { SwitchRow } from "@/components/ui/form";
import { ArrowLeftIcon, CheckIcon, CloseIcon, RefreshIcon, ShieldIcon, WarningIcon } from "@/components/ui/icons";
import { Page } from "@/components/ui/page";
import { PageSkeleton, RequestState } from "@/components/ui/request-state";
import { SectionCard } from "@/components/ui/section-card";
import { m } from "@/i18n";
import { dateTime, shortDate } from "@/lib/format";
import { errorMessage, mutate } from "@/services/api/client";
import type { DeviceDetail, SimLine } from "@/services/api/types";
import { cn } from "@/utils/cn";
import { smsKeys } from "../../api/keys";
import { useDevice, useHeartbeats } from "../../api/queries";
import { DeviceAvatar, DeviceStatusPill, OnlineLabel } from "../device-badges";
import { DeviceAccessManager } from "./access-manager";

const PERMISSIONS = ["RECEIVE_SMS", "READ_SMS", "SEND_SMS", "RECEIVE_MMS", "READ_CONTACTS", "READ_PHONE_STATE", "POST_NOTIFICATIONS"];

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="flex items-start justify-between gap-3 py-2 text-sm"><dt className="text-text-tertiary">{label}</dt><dd className="text-right text-text-primary">{children}</dd></div>;
}

export function DeviceDetailPage({ id }: { id: string }) {
  const device = useDevice(id);
  const data = device.data;
  usePageTitle({ page: "Phone", section: "Devices", detail: data?.name });
  if (device.isPending) return <Page><PageSkeleton /></Page>;
  if (device.error || !data) return <Page><RequestState loading={false} error={errorMessage(device.error)} onRetry={() => device.refetch()} /></Page>;
  return <Detail data={data} />;
}

function Detail({ data }: { data: DeviceDetail }) {
  const client = useQueryClient();
  const { can } = useSession();
  const [confirm, setConfirm] = useState<null | "suspend" | "revoke">(null);
  const [typed, setTyped] = useState("");
  const manage = data.permissions.manage;
  const admin = can("sms.manage_devices");
  const refresh = (next?: DeviceDetail) => {
    if (next) client.setQueryData(smsKeys.device(data.id), next);
    client.invalidateQueries({ queryKey: smsKeys.devices() });
    client.invalidateQueries({ queryKey: ME_KEY });
  };
  const call = async (path: string, body?: unknown, success?: string) => {
    try { const next = await mutate<DeviceDetail>(`sms/devices/${data.id}/${path}`, "POST", body); refresh(next); if (success) toast.success(success); }
    catch (error) { toast.error(errorMessage(error)); throw error; }
  };
  const progress = data.sync_progress as { phase?: string; done?: number; total?: number };

  const restricted = data.battery_optimised || data.background_restricted || (data.standby_bucket ?? 0) >= 40;
  return (
    <Page className="max-w-5xl">
      <ButtonLink href="/sms/devices" appearance="ghost" size="sm" className="mb-3 -ml-2"><ArrowLeftIcon size={16} />All phones</ButtonLink>
      <header className="mb-5 flex flex-wrap items-start gap-4">
        <DeviceAvatar name={data.name} colour={data.office.colour} online={data.online} size={52} />
        <div className="min-w-0 flex-1">
          <h1 className="flex flex-wrap items-center gap-2 text-xl font-semibold text-text-primary sm:text-2xl">{data.name} <DeviceStatusPill status={data.status} online={data.online} /></h1>
          <p className="text-sm text-text-tertiary"><span className="font-mono">{data.code}</span> · {data.office.name} · <OnlineLabel online={data.online} lastSeen={data.last_seen_at} /></p>
        </div>
        {data.status !== "revoked" && (
          <div className="flex flex-wrap gap-2">
            {manage && data.status === "active" && <Button appearance="outline" onPress={async () => { try { await mutate(`sms/devices/${data.id}/resync/`, "POST"); toast.success("The phone will upload its messages again."); } catch (e) { toast.error(errorMessage(e)); } }}><RefreshIcon size={16} />{m.sms.devices.resync}</Button>}
            {admin && data.status === "active" && <Button appearance="outline" onPress={() => setConfirm("suspend")}>{m.sms.devices.suspend}</Button>}
            {admin && data.status === "suspended" && <Button onPress={() => call("resume/", {}, "Phone resumed.")}>{m.sms.devices.resume}</Button>}
            {admin && <Button variant="danger" appearance="outline" onPress={() => { setTyped(""); setConfirm("revoke"); }}>{m.sms.devices.revoke}</Button>}
          </div>
        )}
      </header>

      {data.attention.length > 0 && (
        <div role="status" className="mb-4 flex items-start gap-3 rounded-xl border border-warning-500/40 bg-warning-500/10 p-4 text-sm">
          <WarningIcon className="shrink-0 text-warning-500" />
          <div className="min-w-0 space-y-2">
            <ul className="space-y-0.5">{data.attention.map((alert) => <li key={alert.code} className="text-text-primary">{alert.label}</li>)}</ul>
            {restricted && (
              <div data-background-help="">
                <p className="font-medium text-text-primary">How to fix on this phone{data.manufacturer ? ` (${data.manufacturer})` : ""}</p>
                <ol className="list-decimal space-y-0.5 pl-5 text-text-secondary">{data.background_help.map((step) => <li key={step}>{step}</li>)}</ol>
                <p className="text-text-tertiary">Or open the app on the phone: Settings → Keep messages flowing.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {data.is_simulated && <SimulatorControls data={data} onChange={refresh} />}

      <div className="grid gap-4 lg:grid-cols-2">
        <SectionCard title="Phone">
          <dl className="divide-y divide-card-border">
            <Row label="Model">{[data.manufacturer, data.model].filter(Boolean).join(" ") || "—"}</Row>
            <Row label="Android">{data.android_version || "—"}{data.sdk_int ? ` (API ${data.sdk_int})` : ""}</Row>
            <Row label="App version">{data.app_version || "—"}</Row>
            <Row label="Key">{data.hardware_backed ? <span className="inline-flex items-center gap-1 text-success-600 dark:text-success-400"><ShieldIcon size={14} />Hardware ({data.attestation.security_level})</span> : <span className="text-text-secondary">Not verified as hardware-backed</span>}</Row>
            <Row label="Enrolled">{shortDate(data.enrolled_at)}{data.enrolled_by ? ` by ${data.enrolled_by.display_name}` : ""}</Row>
            <Row label="Notice accepted">{data.notice_accepted_at ? dateTime(data.notice_accepted_at) : "—"}</Row>
            <Row label="Wake-ups">{data.push_enabled ? "Firebase push" : "Polling"}</Row>
          </dl>
        </SectionCard>
        <SectionCard title="Health">
          <dl className="divide-y divide-card-border">
            <Row label="Default SMS app">{data.is_default_sms_app || data.is_simulated ? "Yes" : <span className="text-warning-600 dark:text-warning-400">No</span>}</Row>
            <Row label="Battery">{data.battery === null ? "—" : `${data.battery}%${data.charging ? " · charging" : ""}`}</Row>
            <Row label="Network">{data.network_type || "—"}{data.signal !== null ? ` · signal ${data.signal}/4` : ""}</Row>
            <Row label="Battery optimisation">{data.battery_optimised ? <span className="text-warning-600 dark:text-warning-400">On (may delay messages)</span> : "Off"}</Row>
            <Row label="Background use">{data.background_restricted ? <span className="text-warning-600 dark:text-warning-400">Restricted</span> : "Allowed"}</Row>
            <Row label="Android standby">{standbyLabel(data.standby_bucket)}</Row>
            <Row label="Waiting to upload">{data.pending_outbox}</Row>
            <Row label="Last sync">{data.last_sync_at ? dateTime(data.last_sync_at) : "—"}</Row>
          </dl>
          {progress.phase && progress.phase !== "done" && progress.total ? (
            <div className="mt-3"><p className="mb-1 text-xs text-text-tertiary">Copying message history: {progress.done ?? 0} of {progress.total}</p><Progress progress={Math.round(((progress.done ?? 0) / progress.total) * 100)} withLabel /></div>
          ) : null}
        </SectionCard>
        <Sims data={data} manage={manage} />
        <SectionCard title="Permissions on the phone" description="The app re-checks these every time it starts. A revoked permission raises an alert.">
          <ul className="grid gap-1.5 sm:grid-cols-2">
            {PERMISSIONS.map((name) => {
              const granted = (data.permissions_granted as Record<string, boolean>)[name];
              return (
                <li key={name} className="flex items-center gap-2 text-sm">
                  {granted === false ? <CloseIcon size={14} className="text-error-500" /> : granted ? <CheckIcon size={14} className="text-success-500" /> : <span className="size-3.5 rounded-full border border-card-border" />}
                  <span className={cn("font-mono text-xs", granted === false ? "text-error-600 dark:text-error-400" : "text-text-secondary")}>{name}</span>
                </li>
              );
            })}
          </ul>
        </SectionCard>
        <Options data={data} manage={manage} onSaved={refresh} />
        <Heartbeats id={data.id} />
      </div>
      {manage && <div className="mt-4"><DeviceAccessManager deviceId={data.id} /></div>}

      <ConfirmDialog isOpen={confirm === "suspend"} onOpenChange={(open) => !open && setConfirm(null)} title={`Suspend ${data.name}?`} tone="primary" confirmLabel={m.sms.devices.suspend}
        body="The phone stops syncing and sending until you resume it. Its messages stay on the phone and upload after you resume." onConfirm={() => call("suspend/", { reason: "" }, "Phone suspended.")} />
      <Dialog isOpen={confirm === "revoke"} onOpenChange={(open) => !open && setConfirm(null)} role="alertdialog" className="max-w-md">
        <DialogHeader><DialogTitle>{m.sms.devices.revoke}?</DialogTitle></DialogHeader>
        <p className="mt-2 text-sm text-text-secondary">{m.sms.devices.revokeBody}</p>
        <div className="mt-4"><Field label={m.sms.devices.typeCode(data.code)} value={typed} onChange={setTyped} autoFocus /></div>
        <div className="mt-6 flex justify-end gap-2">
          <Button appearance="outline" onPress={() => setConfirm(null)}>{m.common.cancel}</Button>
          <Button variant="danger" isDisabled={typed.trim().toUpperCase() !== data.code} onPress={async () => { await call("revoke/", { confirm_code: typed, reason: "" }, "Phone removed."); setConfirm(null); }}>{m.sms.devices.revoke}</Button>
        </div>
      </Dialog>
    </Page>
  );
}

function Sims({ data, manage }: { data: DeviceDetail; manage: boolean }) {
  return (
    <SectionCard title="SIM lines" description={data.sims.length > 1 ? "Dual SIM: the admin can choose the line when sending." : undefined}>
      {data.sims.length === 0 ? <p className="text-sm text-text-tertiary">No SIM reported yet.</p> : <ul className="space-y-2">{data.sims.map((line) => <SimRow key={line.id} deviceId={data.id} line={line} manage={manage} />)}</ul>}
    </SectionCard>
  );
}

function SimRow({ deviceId, line, manage }: { deviceId: string; line: SimLine; manage: boolean }) {
  const client = useQueryClient();
  const [name, setName] = useState(line.display_name);
  const save = async () => {
    try { await mutate(`sms/devices/${deviceId}/sims/${line.id}/`, "PATCH", { display_name: name }); client.invalidateQueries({ queryKey: smsKeys.device(deviceId) }); toast.success("SIM renamed."); }
    catch (error) { toast.error(errorMessage(error)); }
  };
  return (
    <li className="flex flex-wrap items-end gap-2 rounded-lg border border-card-border p-3">
      <span className="mb-2.5 size-3 shrink-0 rounded-full" style={{ background: line.colour }} aria-hidden="true" />
      <div className="min-w-0 flex-1">
        {manage ? <Field label={`SIM ${line.slot + 1} · ${line.carrier || "Unknown carrier"}`} value={name} onChange={setName} placeholder={line.carrier} /> : <p className="text-sm font-medium text-text-primary">{line.label}</p>}
        <p className="mt-1 text-xs text-text-tertiary">{line.number || "Number not readable from the SIM"}{line.is_default ? " · default" : ""}</p>
      </div>
      {manage && name !== line.display_name && <Button size="sm" onPress={save}>{m.common.save}</Button>}
    </li>
  );
}

function Options({ data, manage, onSaved }: { data: DeviceDetail; manage: boolean; onSaved: (next: DeviceDetail) => void }) {
  const initial = data.options as { signature_enabled?: boolean; signature?: string; mark_read_on_open?: boolean; backfill_days?: number };
  const [options, setOptions] = useState(initial);
  const dirty = JSON.stringify(options) !== JSON.stringify(initial);
  const save = async () => {
    try { onSaved(await mutate<DeviceDetail>(`sms/devices/${data.id}/`, "PATCH", { options })); toast.success("Options saved."); }
    catch (error) { toast.error(errorMessage(error)); }
  };
  return (
    <SectionCard title="Options" footer={manage && dirty && <div className="flex justify-end"><Button onPress={save}>{m.common.save}</Button></div>}>
      <div className="divide-y divide-card-border">
        <SwitchRow title="Mark read on the phone when opened here" checked={!!options.mark_read_on_open} disabled={!manage} onChange={(v) => setOptions({ ...options, mark_read_on_open: v })} />
        <SwitchRow title="Admin signature" description="Appended to admin messages and counted in the SMS length." checked={!!options.signature_enabled} disabled={!manage} onChange={(v) => setOptions({ ...options, signature_enabled: v })} />
        {options.signature_enabled && <div className="py-3"><Field label="Signature" value={options.signature ?? ""} isDisabled={!manage} onChange={(signature) => setOptions({ ...options, signature })} maxLength={40} /></div>}
        <p className="py-3 text-sm text-text-secondary">History copied at enrollment: last {options.backfill_days ?? 90} days.</p>
      </div>
    </SectionCard>
  );
}

function Heartbeats({ id }: { id: string }) {
  const beats = useHeartbeats(id);
  const rows = (beats.data ?? []).slice(0, 12);
  return (
    <SectionCard title="Recent heartbeats" description="Every 5 minutes while the app's service runs, and on every network change.">
      {rows.length === 0 ? <p className="text-sm text-text-tertiary">No heartbeat yet.</p> : (
        <table className="w-full text-xs">
          <thead className="text-left text-text-tertiary"><tr><th className="py-1 font-medium">Time</th><th className="py-1 font-medium">Battery</th><th className="py-1 font-medium">Network</th><th className="py-1 text-right font-medium">Backlog</th></tr></thead>
          <tbody className="divide-y divide-card-border">
            {rows.map((row) => <tr key={row.created_at}><td className="py-1.5 text-text-secondary">{dateTime(row.created_at)}</td><td className="py-1.5">{row.battery ?? "—"}%</td><td className="py-1.5">{row.network_type || "—"}</td><td className="py-1.5 text-right tabular-nums">{row.pending_outbox}</td></tr>)}
          </tbody>
        </table>
      )}
    </SectionCard>
  );
}

function SimulatorControls({ data, onChange }: { data: DeviceDetail; onChange: (next: DeviceDetail) => void }) {
  const run = async (action: "online" | "offline" | "tick" | "inbound") => {
    try { onChange(await mutate<DeviceDetail>(`sms/devices/${data.id}/simulator/`, "POST", { action })); toast.success(`Simulated phone: ${action}`); }
    catch (error) { toast.error(errorMessage(error)); }
  };
  return (
    <SectionCard className="mb-4" title="Demo phone controls" description="This phone is simulated (demo and tests only). Real phones can't be controlled from here.">
      <div className="flex flex-wrap gap-2" data-simulator-controls="">
        {data.online ? <Button size="sm" appearance="outline" onPress={() => run("offline")}>Go offline</Button> : <Button size="sm" onPress={() => run("online")}>Come online</Button>}
        <Button size="sm" appearance="outline" onPress={() => run("tick")}>Process outbox now</Button>
        <Button size="sm" appearance="outline" onPress={() => run("inbound")}>Receive a text</Button>
      </div>
    </SectionCard>
  );
}

/** UsageStatsManager buckets: from 40 ("rare") Android delays the app's background work by hours. */
function standbyLabel(bucket: number | null) {
  if (bucket === null) return "—";
  const name = bucket <= 10 ? "Active" : bucket <= 20 ? "Working set" : bucket <= 30 ? "Frequent" : bucket < 45 ? "Rare" : "Restricted";
  return bucket >= 40 ? <span className="text-warning-600 dark:text-warning-400">{name} (background work delayed)</span> : name;
}
