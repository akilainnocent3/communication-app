import { MessageIcon } from "@/components/ui/icons";
import { m } from "@/i18n";
import type { PlatformDefinition } from "../types";
import { useSmsBadges } from "./api/queries";
import { useSmsCommands } from "./commands";
import { DeviceSwitcher } from "./components/device-switcher";
import { NewMessageButton } from "./components/new-message";
import { SmsProvider } from "./components/sms-provider";
import { SMS_NAV } from "./nav";

export const sms: PlatformDefinition = {
  key: "sms",
  name: m.platforms.sms.name,
  description: m.platforms.sms.description,
  icon: <MessageIcon />,
  accent: "text-[#10b981]",
  basePath: "/sms",
  homePath: "/sms/inbox",
  permission: "sms.access",
  status: "active",
  nav: SMS_NAV,
  useBadges: useSmsBadges,
  ContextSwitcher: DeviceSwitcher,
  SidebarAction: NewMessageButton,
  Provider: SmsProvider,
  useCommands: useSmsCommands,
};
