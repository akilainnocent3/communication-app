"use client";

import { Button, ListBox, ListBoxItem, Popover, Select, SelectValue, Separator } from "react-aria-components";
import { toast } from "sonner";
import { ChevronDownIcon, MessageIcon, WarningIcon } from "@/components/ui/icons";
import { m } from "@/i18n";
import { cn } from "@/utils/cn";
import { useDeviceScope, useDeviceSummaries } from "../api/queries";
import { DeviceAvatar, attentionLabel } from "./device-badges";

function Count({ value }: { value: number }) {
  if (!value) return null;
  return <span className="ml-auto rounded-full bg-primary-500/10 px-1.5 text-xs font-medium text-primary-600 tabular-nums dark:text-primary-300">{value > 999 ? "999+" : value}</span>;
}

/**
 * SMS's context switcher: "All phones" (unified) or one enrolled phone. Lives at the top of the sidebar and in the
 * mobile context bar; switching remounts the SMS pages (keyed by scope) and shows a toast.
 */
export function DeviceSwitcher({ collapsed = false, compact = false }: { collapsed?: boolean; compact?: boolean }) {
  const [scope, setScope] = useDeviceScope();
  const devices = useDeviceSummaries();
  const current = scope === "all" ? undefined : devices.find((device) => device.id === scope);
  const totalUnread = devices.reduce((sum, device) => sum + device.unread, 0);
  const attention = devices.filter((device) => device.attention.length > 0).length;

  const trigger = current ? (
    <DeviceAvatar name={current.name} colour={current.office.colour} online={current.online} size={collapsed ? 32 : 26} />
  ) : (
    <span className={cn("flex shrink-0 items-center justify-center rounded-full bg-primary-500/10 text-primary-500 dark:text-primary-300", collapsed ? "size-8" : "size-6.5")}><MessageIcon size={16} /></span>
  );

  return (
    <Select
      aria-label="Phone"
      selectedKey={scope}
      onSelectionChange={(key) => {
        const next = String(key);
        if (next === scope) return;
        setScope(next);
        const device = devices.find((item) => item.id === next);
        toast.success(device ? m.sms.viewing(device.name) : m.sms.viewingAll, { duration: 2000 });
      }}
      className={cn("min-w-0", collapsed ? "flex justify-center" : "w-full")}
    >
      <Button
        className={cn(
          "group relative flex min-w-0 items-center rounded-xl border border-card-border bg-card-surface-area text-left transition-colors hover:border-primary-500/40 hover:bg-primary-500/5 focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none",
          collapsed ? "size-11 justify-center p-0" : compact ? "h-9 w-full gap-2 rounded-full px-2.5" : "h-12 w-full gap-2.5 px-2.5",
        )}
      >
        {trigger}
        {!collapsed && (
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium text-text-primary"><SelectValue>{() => current?.name ?? m.sms.allDevices}</SelectValue></span>
            {!compact && <span className="block truncate text-xs text-text-tertiary">{current ? `${current.code} · ${current.online ? m.sms.online : m.sms.offline}` : m.sms.allDevicesHint(devices.length, totalUnread)}</span>}
          </span>
        )}
        {attention > 0 && (
          <span className={cn("flex items-center text-warning-500", collapsed && "absolute -top-1 -right-1 rounded-full bg-card-surface-area")} title={m.sms.needsAttention(attention)}>
            <WarningIcon size={16} /><span className="sr-only">{m.sms.needsAttention(attention)}</span>
          </span>
        )}
        {!collapsed && <ChevronDownIcon className="shrink-0 text-icon-tertiary transition-transform group-data-pressed:rotate-180" />}
      </Button>
      <Popover placement={collapsed ? "right top" : "bottom start"} className="w-(--trigger-width) min-w-72 overflow-hidden rounded-xl border border-card-border bg-card-surface-area shadow-lg outline-none entering:animate-pop-in">
        <ListBox className="max-h-[60vh] overflow-y-auto p-1.5 outline-none">
          <ListBoxItem id="all" textValue={m.sms.allDevices} className="flex cursor-default items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm outline-none data-focused:bg-background-gray-secondary_alt data-selected:bg-primary-500/10">
            <span className="flex size-7 items-center justify-center rounded-full bg-primary-500/10 text-primary-500 dark:text-primary-300"><MessageIcon size={16} /></span>
            <span className="min-w-0 flex-1"><span className="block font-medium text-text-primary">{m.sms.allDevices}</span><span className="block text-xs text-text-tertiary">{m.sms.unified}</span></span>
            <Count value={totalUnread} />
          </ListBoxItem>
          {devices.length > 0 && <Separator className="mx-2 my-1.5 h-px border-0 bg-card-border" />}
          {devices.map((device) => (
            <ListBoxItem key={device.id} id={device.id} textValue={`${device.name} ${device.code}`} className="flex cursor-default items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm outline-none data-focused:bg-background-gray-secondary_alt data-selected:bg-primary-500/10">
              <DeviceAvatar name={device.name} colour={device.office.colour} online={device.online} />
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-1.5 font-medium text-text-primary"><span className="truncate">{device.name}</span>
                  {device.attention.length > 0 && <WarningIcon size={14} className="shrink-0 text-warning-500" aria-label={device.attention.map(attentionLabel).join(", ")} />}
                </span>
                <span className="block truncate text-xs text-text-tertiary">{device.code} · {device.office.name}</span>
              </span>
              <Count value={device.unread} />
            </ListBoxItem>
          ))}
        </ListBox>
      </Popover>
    </Select>
  );
}
