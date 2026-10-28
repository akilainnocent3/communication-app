"use client";

import { PhoneIcon } from "@/components/ui/icons";
import { m } from "@/i18n";
import { PhoneSwitcher } from "../../shared/phone-switcher";
import { useCallsDevices, useCallsScope } from "../api/queries";

/** Calls' context switcher: the shared phone switcher with each phone's live call state. */
export function CallsDeviceSwitcher({ collapsed = false, compact = false }: { collapsed?: boolean; compact?: boolean }) {
  const [scope, setScope] = useCallsScope();
  const devices = useCallsDevices();
  const onCall = devices.filter((device) => device.call_state === "active" || device.call_state === "held").length;
  return (
    <PhoneSwitcher devices={devices} scope={scope} onScopeChange={setScope} icon={<PhoneIcon />} allHint={m.calls.allHint(devices.length, onCall)}
      allSubtitle={m.calls.unified} collapsed={collapsed} compact={compact}
      detail={(device) => `${device.code} · ${device.online ? m.calls.state[device.call_state] ?? m.sms.online : m.sms.offline}`} />
  );
}
