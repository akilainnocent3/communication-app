"use client";

import { useMemo } from "react";
import { AllMailIcon, DashboardIcon, InboxIcon, KeyboardIcon, PencilIcon, PlusIcon, SearchIcon, TagIcon } from "@/components/ui/icons";
import type { CommandDef } from "../types";
import { useLabels, useMailboxScope, useMailboxSummaries } from "./api/queries";
import { openCompose } from "./compose/store";
import { FOLDERS } from "./folders";
import { folderUrl, labelUrl } from "./nav";
import { setMailboxScope } from "./state";
import { openShortcutHelp } from "./shortcuts";

/** Gmail entries for the ⌘K palette: compose, folders, labels, mailboxes, search. */
export function useGmailCommands(): CommandDef[] {
  const [scope] = useMailboxScope();
  const mailboxes = useMailboxSummaries();
  const labels = useLabels(scope === "all" ? undefined : scope);
  return useMemo(() => {
    const commands: CommandDef[] = [
      { id: "gmail.compose", group: "Gmail", title: "Compose new email", icon: <PencilIcon />, shortcut: "c", run: () => openCompose({ mailbox: scope === "all" ? undefined : scope }) },
      { id: "gmail.dashboard", group: "Gmail", title: "Dashboard", icon: <DashboardIcon />, href: "/gmail/dashboard" },
      { id: "gmail.search", group: "Gmail", title: "Search mail", icon: <SearchIcon />, shortcut: "/", keywords: "find query", run: () => document.getElementById("mail-search")?.focus() },
      { id: "gmail.shortcuts", group: "Gmail", title: "Keyboard shortcuts", icon: <KeyboardIcon />, shortcut: "?", run: openShortcutHelp },
      { id: "gmail.add-mailbox", group: "Gmail", title: "Add a mailbox", icon: <PlusIcon />, href: "/gmail/mailboxes/new", permission: "mail.manage_mailboxes" },
      ...FOLDERS.map((folder) => ({ id: `gmail.folder.${folder.key}`, group: "Go to folder", title: folder.title, icon: folder.icon, href: folderUrl(folder.key) })),
      ...(labels.data ?? []).filter((label) => label.type === "user").map((label) => ({ id: `gmail.label.${label.label_id}`, group: "Go to label", title: label.name, icon: <TagIcon />, href: labelUrl(label.label_id) })),
      { id: "gmail.mailbox.all", group: "Switch mailbox", title: "All mailboxes", icon: <AllMailIcon />, run: () => setMailboxScope("all") },
      ...mailboxes.map((box) => ({ id: `gmail.mailbox.${box.id}`, group: "Switch mailbox", title: box.name, keywords: box.email, icon: <InboxIcon />, run: () => setMailboxScope(box.id) })),
    ];
    return commands;
  }, [scope, mailboxes, labels.data]);
}
