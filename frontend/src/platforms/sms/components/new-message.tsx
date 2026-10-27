"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Dialog, DialogHeader, DialogTitle } from "@/components/tailgrids/core/dialog";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/tailgrids/core/tooltip";
import { SelectField } from "@/components/ui/form";
import { PencilIcon } from "@/components/ui/icons";
import { m } from "@/i18n";
import { cn } from "@/utils/cn";
import { useCurrentDevice, useDevice, useDeviceSummaries } from "../api/queries";
import { closeNewMessage, openNewMessage, useNewMessage } from "../compose-store";
import { Composer } from "./chat/composer";

/** Plausible phone number or short code while typing (the server validates for real). */
const NUMBER = /^\+?[\d\s()-]{3,20}$/;

export function NewMessageDialog() {
  const init = useNewMessage();
  if (!init) return null;
  return <NewMessage key={JSON.stringify(init)} initialDevice={init.device} initialTo={init.to} />;
}

function NewMessage({ initialDevice, initialTo }: { initialDevice?: string; initialTo?: string }) {
  const router = useRouter();
  const devices = useDeviceSummaries().filter((device) => device.permissions.send && device.status === "active");
  const [deviceId, setDeviceId] = useState(initialDevice && devices.some((d) => d.id === initialDevice) ? initialDevice : devices[0]?.id ?? "");
  const [to, setTo] = useState(initialTo ?? "");
  const device = useDevice(deviceId || undefined);
  const valid = NUMBER.test(to.trim());
  return (
    <Dialog isOpen onOpenChange={(open) => !open && closeNewMessage()} className="max-w-xl p-0" aria-label={m.sms.composer.newTitle}>
      <div className="px-6 pt-6">
        <DialogHeader><DialogTitle>{m.sms.composer.newTitle}</DialogTitle></DialogHeader>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <SelectField label={m.sms.composer.device} value={deviceId} onChange={(event) => setDeviceId(event.target.value)}
            options={devices.map((d) => ({ value: d.id, label: `${d.name} (${d.code})` }))} />
          <label className="flex min-w-0 flex-col gap-2 text-sm">
            <span className="font-medium text-text-primary">{m.sms.composer.to}</span>
            <input value={to} onChange={(event) => setTo(event.target.value)} inputMode="tel" autoComplete="off" placeholder={m.sms.composer.toPlaceholder} autoFocus
              aria-invalid={!!to && !valid} className="h-10.5 rounded-lg border border-card-border bg-input-background px-3.5 text-sm text-text-primary outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-500/20" />
          </label>
        </div>
      </div>
      <div className="mt-4">
        <Composer device={device.data} to={[to.trim()]} canSend={!!deviceId} recipientsReady={valid}
          onSent={(result) => { closeNewMessage(); router.push(`/sms/inbox?c=${result.conversation}`); }} />
      </div>
    </Dialog>
  );
}

/** Sidebar's prominent "New message" button. */
export function NewMessageButton({ collapsed, onAction }: { collapsed: boolean; onAction?: () => void }) {
  const current = useCurrentDevice();
  const devices = useDeviceSummaries();
  const canSend = current ? current.permissions.send && current.status === "active" : devices.some((d) => d.permissions.send && d.status === "active");
  if (!canSend) return null;
  const open = () => { openNewMessage({ device: current?.id }); onAction?.(); };
  const className = "flex items-center justify-center gap-2 rounded-xl bg-primary-500 font-medium text-white shadow-[0_6px_16px_-6px_rgba(55,88,249,0.55)] transition hover:bg-primary-600 focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2 focus-visible:ring-offset-card-surface-area focus-visible:outline-none active:scale-[0.98]";
  if (collapsed)
    return (
      <Tooltip placement="right">
        <TooltipTrigger asChild><button type="button" onClick={open} aria-label={`${m.sms.newMessage} (c)`} className={cn(className, "size-11")}><PencilIcon /></button></TooltipTrigger>
        <TooltipContent><p>{m.sms.newMessage}</p></TooltipContent>
      </Tooltip>
    );
  return (
    <button type="button" onClick={open} className={cn(className, "h-11 w-full text-sm")}>
      <PencilIcon /> {m.sms.newMessage}
      <kbd className="ml-1 rounded border border-white/30 px-1.5 text-[11px] leading-4 font-normal text-white/80">c</kbd>
    </button>
  );
}
