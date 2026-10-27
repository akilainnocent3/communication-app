import { MediaIcon, PhoneIcon } from "@/components/ui/icons";
import { m } from "@/i18n";
import type { PlatformDefinition } from "./types";

function comingSoon(key: "calls" | "media", icon: React.ReactNode): PlatformDefinition {
  return {
    key, name: m.platforms[key].name, description: m.platforms[key].description, icon,
    accent: "text-text-tertiary", basePath: `/${key}`, homePath: `/${key}`, permission: `${key}.access`, status: "coming_soon", nav: [],
  };
}

export const callsComingSoon = comingSoon("calls", <PhoneIcon />);
export const mediaComingSoon = comingSoon("media", <MediaIcon />);
