import { PhoneIcon } from "@/components/ui/icons";
import { m } from "@/i18n";
import type { PlatformDefinition } from "../types";
import { useCallsBadges } from "./api/queries";
import { useCallsCommands } from "./commands";
import { CallsDeviceSwitcher } from "./components/device-switcher";
import { CALLS_NAV } from "./nav";

export const calls: PlatformDefinition = {
  key: "calls",
  name: m.platforms.calls.name,
  description: m.platforms.calls.description,
  icon: <PhoneIcon />,
  accent: "text-[#3758f9]",
  basePath: "/calls",
  homePath: "/calls/dashboard",
  permission: "calls.access",
  status: "active",
  nav: CALLS_NAV,
  useBadges: useCallsBadges,
  ContextSwitcher: CallsDeviceSwitcher,
  useCommands: useCallsCommands,
};
