import { BlockIcon, DashboardIcon, GearIcon, OutboxIcon, PlusIcon, ShieldIcon, SmartphoneIcon, TemplateIcon, UsersIcon, CalendarIcon } from "@/components/ui/icons";
import type { PlatformNavSection } from "../types";
import { FOLDERS } from "./folders";

export const SMS_BASE = "/sms";
export const folderUrl = (key: string) => `${SMS_BASE}/${key}`;

export const SMS_NAV: PlatformNavSection[] = [
  { label: "OVERVIEW", items: [{ title: "Dashboard", icon: <DashboardIcon />, url: `${SMS_BASE}/dashboard` }] },
  {
    label: "MESSAGES",
    items: [
      ...FOLDERS.map((folder) => ({ title: folder.title, icon: folder.icon, url: folderUrl(folder.key), badgeKey: folder.badgeKey })),
      { title: "Outbox", icon: <OutboxIcon />, url: `${SMS_BASE}/outbox`, badgeKey: "outbox" },
      { title: "Scheduled", icon: <CalendarIcon />, url: `${SMS_BASE}/scheduled` },
    ],
  },
  {
    label: "CONTACTS",
    items: [
      { title: "Contacts", icon: <UsersIcon />, url: `${SMS_BASE}/contacts` },
      { title: "Blocked numbers", icon: <BlockIcon />, url: `${SMS_BASE}/blocked` },
    ],
  },
  {
    label: "DEVICES",
    items: [
      { title: "Phones", icon: <SmartphoneIcon />, url: `${SMS_BASE}/devices`, badgeKey: "attention" },
      { title: "Enroll phone", icon: <PlusIcon />, url: `${SMS_BASE}/devices/enroll`, permission: "sms.manage_devices" },
    ],
  },
  {
    label: "TOOLS",
    items: [
      { title: "Quick replies", icon: <TemplateIcon />, url: `${SMS_BASE}/tools/quick-replies` },
      { title: "Sensitive-message rules", icon: <ShieldIcon />, url: `${SMS_BASE}/tools/rules` },
      { title: "SMS settings", icon: <GearIcon />, url: `${SMS_BASE}/tools/settings` },
    ],
  },
];
