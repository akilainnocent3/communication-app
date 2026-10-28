"use client";

import { MessageIcon } from "@/components/ui/icons";
import { m } from "@/i18n";
import { PhoneSwitcher } from "../../shared/phone-switcher";
import { useDeviceScope, useDeviceSummaries } from "../api/queries";

/**
 * SMS's context switcher: "All phones" (unified) or one enrolled phone. Switching remounts the SMS pages (keyed by
 * scope) and shows a toast. The markup is the shared PhoneSwitcher (Calls uses it too).
 */
export function DeviceSwitcher({ collapsed = false, compact = false }: { collapsed?: boolean; compact?: boolean }) {
  const [scope, setScope] = useDeviceScope();
  const devices = useDeviceSummaries();
  const totalUnread = devices.reduce((sum, device) => sum + device.unread, 0);
  return (
    <PhoneSwitcher devices={devices} scope={scope} onScopeChange={setScope} icon={<MessageIcon />} count={(device) => device.unread}
      allHint={m.sms.allDevicesHint(devices.length, totalUnread)} allSubtitle={m.sms.unified} collapsed={collapsed} compact={compact} />
  );
}
