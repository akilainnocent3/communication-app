"use client";

import { useMemo } from "react";
import { CallMissedIcon, CallbackIcon, DashboardIcon, LiveIcon, PhoneIcon, SmartphoneIcon, UsersIcon } from "@/components/ui/icons";
import { m } from "@/i18n";
import type { CommandDef } from "../types";
import { useCallsDevices } from "./api/queries";
import { callbacksUrl, logUrl } from "./nav";
import { setCallsScope } from "./state";

/** Calls entries for the ⌘K palette. */
export function useCallsCommands(): CommandDef[] {
  const devices = useCallsDevices();
  return useMemo(() => [
    { id: "calls.dashboard", group: "Calls", title: "Calls dashboard", icon: <DashboardIcon />, href: "/calls/dashboard" },
    { id: "calls.live", group: "Calls", title: "Live phones", icon: <LiveIcon />, href: "/calls/live", keywords: "board on call ringing" },
    { id: "calls.unreturned", group: "Calls", title: "Unreturned missed calls", icon: <CallMissedIcon />, href: logUrl("unreturned"), keywords: "call back" },
    { id: "calls.callbacks", group: "Calls", title: "Open call-backs", icon: <CallbackIcon />, href: callbacksUrl("open") },
    { id: "calls.customers", group: "Calls", title: "Customer directory", icon: <UsersIcon />, href: "/calls/customers", keywords: "contacts" },
    ...Object.entries(m.calls.folders).map(([key, title]) => ({ id: `calls.folder.${key}`, group: "Go to calls", title, icon: <PhoneIcon />, href: logUrl(key) })),
    { id: "calls.device.all", group: "Switch phone", title: m.sms.allDevices, icon: <PhoneIcon />, run: () => setCallsScope("all") },
    ...devices.map((device) => ({ id: `calls.device.${device.id}`, group: "Switch phone", title: device.name, keywords: `${device.code} ${device.office.name}`, icon: <SmartphoneIcon />, run: () => setCallsScope(device.id) })),
  ], [devices]);
}
