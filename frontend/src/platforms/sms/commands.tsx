"use client";

import { useMemo } from "react";
import { DashboardIcon, KeyboardIcon, MessageIcon, OutboxIcon, PencilIcon, PlusIcon, SmartphoneIcon } from "@/components/ui/icons";
import { m } from "@/i18n";
import type { CommandDef } from "../types";
import { useDeviceScope, useDeviceSummaries } from "./api/queries";
import { openNewMessage } from "./compose-store";
import { FOLDERS } from "./folders";
import { folderUrl } from "./nav";
import { openSmsShortcutHelp } from "./shortcuts";
import { setDeviceScope } from "./state";

/** SMS entries for the ⌘K palette: new message, folders, outbox, phones. */
export function useSmsCommands(): CommandDef[] {
  const [scope] = useDeviceScope();
  const devices = useDeviceSummaries();
  return useMemo(() => [
    { id: "sms.new", group: "SMS", title: m.sms.newMessage, icon: <PencilIcon />, shortcut: "c", keywords: "compose text send", run: () => openNewMessage({ device: scope === "all" ? undefined : scope }) },
    { id: "sms.dashboard", group: "SMS", title: "SMS dashboard", icon: <DashboardIcon />, href: "/sms/dashboard" },
    { id: "sms.outbox", group: "SMS", title: "Outbox", icon: <OutboxIcon />, href: "/sms/outbox", keywords: "queued failed" },
    { id: "sms.devices", group: "SMS", title: "Phones", icon: <SmartphoneIcon />, href: "/sms/devices", keywords: "devices" },
    { id: "sms.enroll", group: "SMS", title: "Enroll a phone", icon: <PlusIcon />, href: "/sms/devices/enroll", permission: "sms.manage_devices" },
    { id: "sms.shortcuts", group: "SMS", title: "Keyboard shortcuts", icon: <KeyboardIcon />, shortcut: "?", run: openSmsShortcutHelp },
    ...FOLDERS.map((folder) => ({ id: `sms.folder.${folder.key}`, group: "Go to folder", title: folder.title, icon: folder.icon, href: folderUrl(folder.key) })),
    { id: "sms.device.all", group: "Switch phone", title: m.sms.allDevices, icon: <MessageIcon />, run: () => setDeviceScope("all") },
    ...devices.map((device) => ({ id: `sms.device.${device.id}`, group: "Switch phone", title: device.name, keywords: `${device.code} ${device.office.name}`, icon: <SmartphoneIcon />, run: () => setDeviceScope(device.id) })),
    ...devices.map((device) => ({ id: `sms.open.${device.id}`, group: "Open phone", title: `${device.name} (${device.code})`, keywords: device.code, icon: <SmartphoneIcon />, href: `/sms/devices/${device.id}` })),
  ], [scope, devices]);
}
