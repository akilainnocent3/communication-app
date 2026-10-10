"use client";

import { DashboardIcon, FilterIcon, InboxIcon, PlusIcon, SignatureIcon, TagIcon, TemplateIcon, VacationIcon } from "@/components/ui/icons";
import type { PlatformNavItem, PlatformNavSection } from "../types";
import { useLabels, useMailboxScope } from "./api/queries";
import { FOLDERS } from "./folders";

export const GMAIL_BASE = "/gmail";
export const folderUrl = (key: string) => `${GMAIL_BASE}/${key}`;
export const labelUrl = (labelId: string) => `${GMAIL_BASE}/label/${encodeURIComponent(labelId)}`;

/** LABELS section: the selected mailbox's user labels (hidden for "All mailboxes"). */
function useLabelItems(): PlatformNavItem[] {
  const [scope] = useMailboxScope();
  const labels = useLabels(scope === "all" ? undefined : scope);
  if (scope === "all") return [];
  const items: PlatformNavItem[] = (labels.data ?? [])
    .filter((label) => label.type === "user")
    .map((label) => ({ title: label.name, icon: <TagIcon />, url: labelUrl(label.label_id), dot: label.colour || "#9ca3af", badgeKey: `label:${label.label_id}` }));
  return [...items, { title: "New label", icon: <PlusIcon />, url: `${GMAIL_BASE}/labels?new=1`, permission: "mail.access" }];
}

export const GMAIL_NAV: PlatformNavSection[] = [
  { label: "OVERVIEW", items: [{ title: "Dashboard", icon: <DashboardIcon />, url: `${GMAIL_BASE}/dashboard` }] },
  {
    label: "MAIL",
    items: FOLDERS.map((folder) => ({ title: folder.title, icon: folder.icon, url: folderUrl(folder.key), badgeKey: folder.badgeKey })),
  },
  { label: "LABELS", items: useLabelItems },
  {
    label: "MAILBOXES",
    items: [
      { title: "Connected mailboxes", icon: <InboxIcon />, url: `${GMAIL_BASE}/mailboxes` },
      { title: "Add mailbox", icon: <PlusIcon />, url: `${GMAIL_BASE}/mailboxes/new`, permission: "mail.manage_mailboxes" },
    ],
  },
  {
    label: "TOOLS",
    items: [
      { title: "Templates", icon: <TemplateIcon />, url: `${GMAIL_BASE}/tools/templates` },
      { title: "Labels", icon: <TagIcon />, url: `${GMAIL_BASE}/labels` },
      { title: "Filters & rules", icon: <FilterIcon />, url: `${GMAIL_BASE}/tools/filters` },
      { title: "Signatures", icon: <SignatureIcon />, url: `${GMAIL_BASE}/tools/signatures` },
      { title: "Vacation responder", icon: <VacationIcon />, url: `${GMAIL_BASE}/tools/vacation` },
    ],
  },
];
