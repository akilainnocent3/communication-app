"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { DropdownMenu, DropdownMenuContent, DropdownMenuHeader, DropdownMenuItem, DropdownMenuTrigger } from "@/components/tailgrids/core/dropdown";
import { ChevronDownIcon, GearIcon, KeyboardIcon, LogoutIcon } from "@/components/ui/icons";
import { m } from "@/i18n";
import { initials } from "@/lib/format";
import { errorMessage } from "@/services/api/client";
import { openShortcutHelp } from "@/platforms/gmail/shortcuts";
import { useSession } from "./session-provider";

export function UserMenu({ compact = false }: { compact?: boolean }) {
  const session = useSession();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  if (!session.me) return null;
  const { display_name: name, email } = session.me.user;
  async function signOut() {
    setBusy(true);
    try { await session.signOut(); router.replace("/login"); } catch (error) { toast.error(errorMessage(error)); } finally { setBusy(false); }
  }
  const avatar = <span aria-hidden="true" className="flex size-10 items-center justify-center rounded-lg border border-border-secondary-alt bg-background-gray-secondary_alt text-sm font-semibold text-text-primary">{initials(name)}</span>;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger aria-label={m.shell.account} className="group flex items-center gap-2.5 rounded-lg focus-visible:ring-2 focus-visible:ring-primary-500">
        {avatar}
        {!compact && <span className="hidden max-w-36 truncate text-sm font-medium text-text-primary 2xl:inline">{name}</span>}
        <ChevronDownIcon className="text-icon-tertiary transition-transform duration-200 group-aria-expanded:-rotate-180" />
      </DropdownMenuTrigger>
      <DropdownMenuContent placement="bottom end" className="w-72 overflow-hidden p-0 shadow-lg">
        <DropdownMenuHeader className="flex items-center gap-2.5 border-b border-border-secondary-alt px-4 py-3">
          {avatar}
          <span className="min-w-0">
            <span className="block truncate text-sm font-medium text-text-primary">{name}</span>
            <span className="block truncate text-xs text-text-tertiary">{email} · {session.me.role?.name ?? "Staff"}</span>
          </span>
        </DropdownMenuHeader>
        <div className="p-1.5">
          <DropdownMenuItem href="/settings/preferences" className="cursor-pointer px-3 py-2.5"><GearIcon className="text-icon-secondary" />{m.shell.preferences}</DropdownMenuItem>
          <DropdownMenuItem onAction={openShortcutHelp} className="cursor-pointer px-3 py-2.5"><KeyboardIcon className="text-icon-secondary" />Keyboard shortcuts</DropdownMenuItem>
          <DropdownMenuItem onAction={signOut} isDisabled={busy} className="cursor-pointer px-3 py-2.5"><LogoutIcon className="text-icon-secondary" />{busy ? m.auth.signingOut : m.auth.signOut}</DropdownMenuItem>
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
