"use client";

import { Command } from "cmdk";
import { useTheme } from "next-themes";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { CommandIcon, LayersIcon, MoonIcon, SearchIcon } from "@/components/ui/icons";
import { m } from "@/i18n";
import { canSee } from "@/lib/permissions";
import { PLATFORMS, type CommandDef } from "@/platforms/registry";
import { useActivePlatform, platformEntry } from "./active-platform";
import { startNavigationPending } from "./navigation-pending";
import { useSession } from "./session-provider";
import { SETTINGS_NAV } from "./settings-nav";

const noCommands = () => [] as CommandDef[];

/** ⌘K / Ctrl+K: the active platform's commands merged with global ones (settings pages, platforms, theme). */
export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const { me } = useSession();
  const { resolvedTheme, setTheme } = useTheme();
  const platform = useActivePlatform();
  const platformCommands = (platform.useCommands ?? noCommands)();
  const restore = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((value) => { if (!value) restore.current = document.activeElement as HTMLElement | null; return !value; });
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const commands = useMemo(() => {
    const global: CommandDef[] = [
      ...SETTINGS_NAV.map((item) => ({ id: `settings.${item.url}`, group: "Settings", title: item.title, icon: item.icon, href: item.url, permission: item.permission })),
      ...PLATFORMS.filter((item) => item.status === "active" && item.key !== platform.key).map((item) => ({ id: `platform.${item.key}`, group: "Platforms", title: `Switch to ${item.name}`, icon: <LayersIcon />, href: platformEntry(item) })),
      { id: "theme", group: "General", title: resolvedTheme === "dark" ? "Switch to light theme" : "Switch to dark theme", icon: <MoonIcon />, keywords: "dark light mode", run: () => setTheme(resolvedTheme === "dark" ? "light" : "dark") },
    ];
    return [...platformCommands, ...global].filter((command) => canSee(me?.permissions, command.permission));
  }, [platformCommands, platform.key, resolvedTheme, setTheme, me?.permissions]);

  const groups = useMemo(() => {
    const map = new Map<string, CommandDef[]>();
    for (const command of commands) map.set(command.group, [...(map.get(command.group) ?? []), command]);
    return [...map.entries()];
  }, [commands]);

  function close() { setOpen(false); restore.current?.focus?.(); }
  function choose(command: CommandDef) {
    setOpen(false);
    if (command.href) { startNavigationPending(command.href); router.push(command.href); }
    else command.run?.({ navigate: (href) => router.push(href), setTheme, theme: resolvedTheme });
  }

  return (
    <>
      <button
        type="button"
        onClick={() => { restore.current = document.activeElement as HTMLElement | null; setOpen(true); }}
        className="inline-flex h-10 items-center gap-2 rounded-lg border border-card-border px-3 text-sm text-text-tertiary transition-colors hover:bg-background-gray-secondary_alt hover:text-text-primary focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none"
        aria-label={`${m.shell.palette} (Ctrl+K)`}
      >
        <CommandIcon size={16} />
        <kbd className="rounded border border-card-border px-1.5 py-0.5 font-sans text-[11px] leading-none">⌘K</kbd>
      </button>
      {open && createPortal(
        <div data-cm-modal-open="" className="fixed inset-0 z-9999 flex items-start justify-center bg-black/40 px-4 pt-[12vh] backdrop-blur-[2px] animate-fade-in" onMouseDown={close}>
          <Command
            label={m.shell.palette}
            loop
            className="w-full max-w-lg overflow-hidden rounded-xl border border-card-border bg-card-surface-area text-text-primary shadow-2xl animate-pop-in"
            onMouseDown={(event) => event.stopPropagation()}
            onKeyDown={(event) => { if (event.key === "Escape") { event.preventDefault(); close(); } }}
          >
            <div className="flex items-center gap-2 border-b border-card-border px-4">
              <SearchIcon className="text-icon-tertiary" />
              <Command.Input autoFocus placeholder={m.shell.palettePlaceholder} className="h-12 w-full border-0 bg-transparent px-0 text-sm text-text-primary placeholder:text-text-tertiary focus:ring-0 focus:outline-none" />
              <kbd className="rounded border border-card-border px-1.5 py-0.5 text-[11px] text-text-tertiary">Esc</kbd>
            </div>
            <Command.List className="max-h-[60vh] overflow-y-auto p-2">
              <Command.Empty className="px-3 py-6 text-center text-sm text-text-tertiary">{m.shell.paletteEmpty}</Command.Empty>
              {groups.map(([group, items]) => (
                <Command.Group key={group} heading={group}
                  className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:pt-3 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:text-[11px] [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:text-text-tertiary [&_[cmdk-group-heading]]:uppercase">
                  {items.map((command) => (
                    <Command.Item key={command.id} value={`${group} ${command.title} ${command.keywords ?? ""} ${command.id}`} onSelect={() => choose(command)}
                      className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-sm data-[selected=true]:bg-primary-500/10 data-[selected=true]:text-primary-600 dark:data-[selected=true]:text-primary-300">
                      <span className="text-icon-tertiary [&_svg]:size-4">{command.icon}</span>
                      <span className="flex-1 truncate">{command.title}</span>
                      {command.shortcut && <kbd className="rounded border border-card-border px-1.5 text-[11px] text-text-tertiary">{command.shortcut}</kbd>}
                    </Command.Item>
                  ))}
                </Command.Group>
              ))}
            </Command.List>
          </Command>
        </div>,
        document.body,
      )}
    </>
  );
}
