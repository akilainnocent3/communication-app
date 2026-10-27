import type { ReactNode } from "react";
import { ArchiveIcon, AssignIcon, ClockIcon, InboxIcon, SpamIcon, StarIcon, UnreadIcon } from "@/components/ui/icons";
import { m } from "@/i18n";
import type { SmsFolder } from "./api/keys";

export type Folder = { key: SmsFolder; title: string; icon: ReactNode; empty: { title: string; body: string }; badgeKey?: string };

export const FOLDERS: Folder[] = (["inbox", "unread", "awaiting", "assigned", "starred", "archived", "spam"] as const).map((key) => ({
  key,
  title: m.sms.folders[key],
  icon: { inbox: <InboxIcon />, unread: <UnreadIcon />, awaiting: <ClockIcon />, assigned: <AssignIcon />, starred: <StarIcon />, archived: <ArchiveIcon />, spam: <SpamIcon /> }[key],
  empty: m.sms.empty[key],
  badgeKey: key === "inbox" ? "inbox" : undefined,
}));

export const folderByKey = (key: string) => FOLDERS.find((folder) => folder.key === key);
