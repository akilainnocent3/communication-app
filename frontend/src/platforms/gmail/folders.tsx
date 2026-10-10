import type { ReactNode } from "react";
import {
  AllMailIcon, AssignIcon, DraftIcon, ImportantIcon, InboxIcon, SendIcon, SnoozeIcon, SpamIcon, StarIcon, TrashIcon, ClockIcon,
} from "@/components/ui/icons";

export type FolderKey = "inbox" | "starred" | "snoozed" | "important" | "sent" | "scheduled" | "drafts" | "all" | "spam" | "trash" | "assigned";

export type Folder = {
  key: FolderKey;
  title: string;
  /** `label` query value for GET /mail/threads/. Scheduled and drafts have their own pages. */
  label?: string;
  icon: ReactNode;
  empty: { title: string; body: string };
  badgeKey?: string;
};

export const FOLDERS: Folder[] = [
  { key: "inbox", title: "Inbox", label: "INBOX", icon: <InboxIcon />, badgeKey: "inbox", empty: { title: "Inbox zero", body: "Nothing needs your attention here. New mail appears automatically." } },
  { key: "starred", title: "Starred", label: "STARRED", icon: <StarIcon />, empty: { title: "No starred conversations", body: "Star a conversation to find it quickly later. Press s on any message." } },
  { key: "snoozed", title: "Snoozed", label: "SNOOZED", icon: <SnoozeIcon />, empty: { title: "Nothing snoozed", body: "Snooze a conversation to have it come back to the inbox when you need it." } },
  { key: "important", title: "Important", label: "IMPORTANT", icon: <ImportantIcon />, empty: { title: "No important conversations", body: "Mark conversations as important to see them here." } },
  { key: "sent", title: "Sent", label: "SENT", icon: <SendIcon />, empty: { title: "No sent mail", body: "Messages sent from this mailbox appear here." } },
  { key: "scheduled", title: "Scheduled", icon: <ClockIcon />, empty: { title: "Nothing scheduled", body: "Use Schedule send in the compose window to send later." } },
  { key: "drafts", title: "Drafts", icon: <DraftIcon />, badgeKey: "drafts", empty: { title: "No drafts", body: "Drafts are saved automatically while you write." } },
  { key: "all", title: "All mail", label: "ALL", icon: <AllMailIcon />, empty: { title: "No mail yet", body: "When the mailbox syncs, every conversation appears here." } },
  { key: "spam", title: "Spam", label: "SPAM", icon: <SpamIcon />, badgeKey: "spam", empty: { title: "Hooray, no spam here!", body: "Messages marked as spam are deleted after 30 days." } },
  { key: "trash", title: "Trash", label: "TRASH", icon: <TrashIcon />, empty: { title: "Trash is empty", body: "Messages in the trash are deleted forever after 30 days." } },
  { key: "assigned", title: "Assigned to me", label: "ASSIGNED", icon: <AssignIcon />, empty: { title: "Nothing assigned to you", body: "When a colleague assigns you a conversation, it shows up here." } },
];

export const folderByKey = (key: string) => FOLDERS.find((folder) => folder.key === key);

export const CATEGORY_TABS = [
  { key: "primary", title: "Primary" },
  { key: "social", title: "Social" },
  { key: "promotions", title: "Promotions" },
  { key: "updates", title: "Updates" },
] as const;
