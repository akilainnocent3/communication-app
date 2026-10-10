import { BuildingIcon, GearIcon, LayersIcon, PlugIcon, ShieldIcon, UsersIcon } from "@/components/ui/icons";
import type { PlatformNavItem } from "@/platforms/types";

/** Shared SETTINGS section under every platform's nav (permission-filtered). */
export const SETTINGS_NAV: PlatformNavItem[] = [
  { title: "Preferences", icon: <GearIcon />, url: "/settings/preferences" },
  { title: "Users & roles", icon: <UsersIcon />, url: "/settings/users", permission: "identity.manage_users" },
  { title: "Offices", icon: <BuildingIcon />, url: "/settings/offices", permission: "identity.manage_users" },
  { title: "Platforms", icon: <LayersIcon />, url: "/settings/platforms", permission: "platforms.manage_platforms" },
  { title: "Integrations", icon: <PlugIcon />, url: "/settings/integrations", permission: "mail.manage_mailboxes" },
  { title: "Audit log", icon: <ShieldIcon />, url: "/settings/audit", permission: "audit.view_auditevent" },
];
