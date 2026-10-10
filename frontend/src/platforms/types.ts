import type { ComponentType, ReactNode } from "react";

export type PlatformNavChild = { title: string; url: string; permission?: string | string[]; badgeKey?: string };
export type PlatformNavItem = {
  title: string;
  icon: ReactNode;
  url?: string;
  items?: PlatformNavChild[];
  permission?: string | string[];
  badgeKey?: string;
  /** Small colour dot instead of the icon (labels). */
  dot?: string;
};
/** `items` may be a hook (called during render) for dynamic entries such as the selected mailbox's labels. */
export type PlatformNavSection = { label: string; items: PlatformNavItem[] | (() => PlatformNavItem[]); footer?: ComponentType<{ collapsed: boolean; onNavigate?: () => void }> };

export type CommandDef = {
  id: string;
  group: string;
  title: string;
  icon?: ReactNode;
  keywords?: string;
  shortcut?: string;
  permission?: string | string[];
  /** Either a URL to open or an action to run. */
  href?: string;
  run?: (ctx: CommandContext) => void;
};
export type CommandContext = { navigate: (href: string) => void; setTheme: (theme: string) => void; theme: string | undefined };

export interface PlatformDefinition {
  key: "gmail" | "sms" | "calls" | "media" | (string & {});
  name: string;
  description: string;
  icon: ReactNode;
  /** Tailwind classes (token-based) for the switcher chip of this platform. */
  accent: string;
  basePath: `/${string}`;
  /** Platform home inside basePath. */
  homePath: `/${string}`;
  permission: string;
  status: "active" | "coming_soon";
  nav: PlatformNavSection[];
  useBadges?: () => Record<string, number>;
  /** Rendered under the brand at the top of the sidebar (Gmail: mailbox switcher). */
  ContextSwitcher?: ComponentType<{ collapsed?: boolean; compact?: boolean }>;
  /** Prominent action under the context switcher (Gmail: Compose). */
  SidebarAction?: ComponentType<{ collapsed: boolean; onAction?: () => void }>;
  /** Wraps the platform's pages and the shell while it is active (stores, compose windows, shortcuts). */
  Provider?: ComponentType<{ children: ReactNode }>;
  /** Hook returning the platform's ⌘K commands (may depend on live data, e.g. mailboxes). */
  useCommands?: () => CommandDef[];
}
