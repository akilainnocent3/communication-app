import { CallIncomingIcon, CallMissedIcon, CallOutgoingIcon, CallbackIcon, CheckCircleIcon, ClockIcon, CoinsIcon, DashboardIcon, DownloadIcon, LiveIcon, MessageIcon, MoonClockIcon, PhoneIcon, SmartphoneIcon, TagIcon, UserIcon, UsersIcon, WarningIcon } from "@/components/ui/icons";
import type { PlatformNavSection } from "../types";

export const CALLS_BASE = "/calls";
export const logUrl = (folder: string) => `${CALLS_BASE}/log/${folder}`;
export const callbacksUrl = (view: string) => `${CALLS_BASE}/callbacks/${view}`;

export const CALLS_NAV: PlatformNavSection[] = [
  {
    label: "OVERVIEW",
    items: [
      { title: "Dashboard", icon: <DashboardIcon />, url: `${CALLS_BASE}/dashboard` },
      { title: "Live", icon: <LiveIcon />, url: `${CALLS_BASE}/live` },
    ],
  },
  {
    label: "CALLS",
    items: [
      { title: "All calls", icon: <PhoneIcon />, url: logUrl("all") },
      { title: "Missed", icon: <CallMissedIcon />, url: logUrl("missed") },
      { title: "Unreturned", icon: <WarningIcon />, url: logUrl("unreturned"), badgeKey: "unreturned" },
      { title: "Incoming", icon: <CallIncomingIcon />, url: logUrl("incoming") },
      { title: "Outgoing", icon: <CallOutgoingIcon />, url: logUrl("outgoing") },
      { title: "After hours", icon: <MoonClockIcon />, url: logUrl("after_hours") },
    ],
  },
  {
    label: "CALLBACKS",
    items: [
      { title: "Open", icon: <CallbackIcon />, url: callbacksUrl("open"), badgeKey: "callbacks" },
      { title: "Assigned to me", icon: <UserIcon />, url: callbacksUrl("mine"), badgeKey: "mine" },
      { title: "Done", icon: <CheckCircleIcon />, url: callbacksUrl("done") },
    ],
  },
  { label: "CUSTOMERS", items: [{ title: "Directory", icon: <UsersIcon />, url: `${CALLS_BASE}/customers` }] },
  { label: "DEVICES", items: [{ title: "Phones", icon: <SmartphoneIcon />, url: `${CALLS_BASE}/devices`, badgeKey: "attention" }] },
  {
    label: "TOOLS",
    items: [
      { title: "Outcomes", icon: <TagIcon />, url: `${CALLS_BASE}/tools/outcomes` },
      { title: "Office hours", icon: <ClockIcon />, url: `${CALLS_BASE}/tools/hours` },
      { title: "Missed-call SMS", icon: <MessageIcon />, url: `${CALLS_BASE}/tools/missed-sms` },
      { title: "Tariffs", icon: <CoinsIcon />, url: `${CALLS_BASE}/tools/tariffs` },
      { title: "Export", icon: <DownloadIcon />, url: `${CALLS_BASE}/tools/export`, permission: "calls.export" },
    ],
  },
];
