import { MailIcon } from "@/components/ui/icons";
import { m } from "@/i18n";
import type { PlatformDefinition } from "../types";
import { useMailBadges } from "./api/queries";
import { useGmailCommands } from "./commands";
import { ComposeButton } from "./components/compose-button";
import { GmailProvider } from "./components/gmail-provider";
import { MailboxSwitcher } from "./components/mailbox-switcher";
import { GMAIL_NAV } from "./nav";

export const gmail: PlatformDefinition = {
  key: "gmail",
  name: m.platforms.gmail.name,
  description: m.platforms.gmail.description,
  icon: <MailIcon />,
  accent: "text-[#ea4335]",
  basePath: "/gmail",
  homePath: "/gmail/inbox",
  permission: "mail.access",
  status: "active",
  nav: GMAIL_NAV,
  useBadges: useMailBadges,
  ContextSwitcher: MailboxSwitcher,
  SidebarAction: ComposeButton,
  Provider: GmailProvider,
  useCommands: useGmailCommands,
};
