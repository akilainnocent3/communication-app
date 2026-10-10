"use client";

import { Button, ListBox, ListBoxItem, Popover, Select, SelectValue, Separator } from "react-aria-components";
import { toast } from "sonner";
import { AllMailIcon, ChevronDownIcon, WarningIcon } from "@/components/ui/icons";
import { cn } from "@/utils/cn";
import { useMailboxScope, useMailboxSummaries } from "../api/queries";
import { MailboxAvatar } from "./mailbox-badges";

function Count({ value }: { value: number }) {
  if (!value) return null;
  return <span className="ml-auto rounded-full bg-primary-500/10 px-1.5 text-xs font-medium text-primary-600 tabular-nums dark:text-primary-300">{value > 999 ? "999+" : value}</span>;
}

/**
 * Gmail's context switcher: "All mailboxes" (unified) or one office mailbox. Lives at the top of the sidebar and
 * in the mobile context bar; switching remounts the mail pages (keyed by scope) and shows a toast.
 */
export function MailboxSwitcher({ collapsed = false, compact = false }: { collapsed?: boolean; compact?: boolean }) {
  const [scope, setScope] = useMailboxScope();
  const mailboxes = useMailboxSummaries();
  const current = scope === "all" ? undefined : mailboxes.find((box) => box.id === scope);
  const totalUnread = mailboxes.reduce((sum, box) => sum + box.unread, 0);
  const attention = mailboxes.filter((box) => box.status === "needs_reconnect" || box.status === "error").length;

  const trigger = current ? (
    <MailboxAvatar name={current.name} colour={current.colour} size={collapsed ? 32 : 26} />
  ) : (
    <span className={cn("flex shrink-0 items-center justify-center rounded-full bg-primary-500/10 text-primary-500 dark:text-primary-300", collapsed ? "size-8" : "size-6.5")}><AllMailIcon size={16} /></span>
  );

  return (
    <Select
      aria-label="Mailbox"
      selectedKey={String(scope)}
      onSelectionChange={(key) => {
        const next = key === "all" ? "all" : Number(key);
        if (next === scope) return;
        setScope(next);
        const box = mailboxes.find((item) => item.id === next);
        toast.success(box ? `Viewing ${box.name}` : "Viewing all mailboxes", { duration: 2000 });
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
            <span className="block truncate text-sm font-medium text-text-primary"><SelectValue>{() => current?.name ?? "All mailboxes"}</SelectValue></span>
            {!compact && <span className="block truncate text-xs text-text-tertiary">{current ? current.email : `${mailboxes.length} mailboxes · ${totalUnread} unread`}</span>}
          </span>
        )}
        {attention > 0 && (
          <span className={cn("flex items-center text-warning-500", collapsed && "absolute -top-1 -right-1 rounded-full bg-card-surface-area")} title={`${attention} mailbox${attention > 1 ? "es" : ""} need attention`}>
            <WarningIcon size={16} /><span className="sr-only">{attention} mailboxes need attention</span>
          </span>
        )}
        {!collapsed && <ChevronDownIcon className="shrink-0 text-icon-tertiary transition-transform group-data-pressed:rotate-180" />}
      </Button>
      <Popover placement={collapsed ? "right top" : "bottom start"} className="w-(--trigger-width) min-w-72 overflow-hidden rounded-xl border border-card-border bg-card-surface-area shadow-lg outline-none entering:animate-pop-in">
        <ListBox className="max-h-[60vh] overflow-y-auto p-1.5 outline-none">
          <ListBoxItem id="all" textValue="All mailboxes" className="flex cursor-default items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm outline-none data-focused:bg-background-gray-secondary_alt data-selected:bg-primary-500/10">
            <span className="flex size-7 items-center justify-center rounded-full bg-primary-500/10 text-primary-500 dark:text-primary-300"><AllMailIcon size={16} /></span>
            <span className="min-w-0 flex-1"><span className="block font-medium text-text-primary">All mailboxes</span><span className="block text-xs text-text-tertiary">Unified inbox</span></span>
            <Count value={totalUnread} />
          </ListBoxItem>
          {mailboxes.length > 0 && <Separator className="mx-2 my-1.5 h-px border-0 bg-card-border" />}
          {mailboxes.map((box) => (
            <ListBoxItem key={box.id} id={String(box.id)} textValue={`${box.name} ${box.email}`} className="flex cursor-default items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm outline-none data-focused:bg-background-gray-secondary_alt data-selected:bg-primary-500/10">
              <MailboxAvatar name={box.name} colour={box.colour} />
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-1.5 font-medium text-text-primary"><span className="truncate">{box.name}</span>
                  {(box.status === "needs_reconnect" || box.status === "error") && <WarningIcon size={14} className="shrink-0 text-warning-500" aria-label="Needs attention" />}
                </span>
                <span className="block truncate text-xs text-text-tertiary">{box.email}</span>
              </span>
              <Count value={box.unread} />
            </ListBoxItem>
          ))}
        </ListBox>
      </Popover>
    </Select>
  );
}
