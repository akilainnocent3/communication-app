"use client";

import { useState } from "react";
import { toast } from "sonner";
import { usePageTitle } from "@/components/shell/trail";
import { useSession } from "@/components/shell/session-provider";
import { Button } from "@/components/tailgrids/core/button";
import { Page, PageHeader } from "@/components/ui/page";
import { RequestState } from "@/components/ui/request-state";
import { SectionCard } from "@/components/ui/section-card";
import { errorMessage } from "@/services/api/client";
import type { CallSettings } from "@/services/api/types";
import { useCallsWrite } from "@/platforms/calls/api/actions";
import { callsKeys } from "@/platforms/calls/api/keys";
import { useCallSettings } from "@/platforms/calls/api/queries";

const INPUT = "h-9 rounded-lg border border-card-border bg-card-surface-area px-2 text-sm text-text-primary disabled:opacity-60";

export default function MissedSmsPage() {
  usePageTitle({ page: "Missed-call SMS", section: "Calls" });
  const settings = useCallSettings();
  return (
    <Page>
      <PageHeader eyebrow="Tools" title="Missed-call SMS and call rules" description="An automatic SMS after a missed call, the call-back window, the post-call card and retention." />
      {settings.isPending || settings.error ? <RequestState loading={settings.isPending} error={settings.error ? errorMessage(settings.error) : undefined} onRetry={() => settings.refetch()} />
        : <SettingsForm key={JSON.stringify(settings.data)} initial={settings.data!} />}
    </Page>
  );
}

function SettingsForm({ initial }: { initial: CallSettings }) {
  const { can } = useSession();
  const disabled = !can("calls.manage_settings");
  const write = useCallsWrite<CallSettings>(callsKeys.settings());
  const [values, setValues] = useState(initial);
  const set = <K extends keyof CallSettings>(key: K, value: CallSettings[K]) => setValues({ ...values, [key]: value });
  const number = (key: keyof CallSettings, label: string, min: number, max: number, hint?: string) => (
    <label className="grid gap-1 text-sm"><span className="font-medium">{label}</span>
      <input disabled={disabled} type="number" min={min} max={max} value={(values[key] as number | null) ?? ""} onChange={(e) => set(key, (e.target.value === "" ? null : Number(e.target.value)) as never)} className={INPUT} />
      {hint && <span className="text-xs text-text-tertiary">{hint}</span>}
    </label>
  );
  return (
    <form className="space-y-4" onSubmit={(e) => {
      e.preventDefault();
      const { effective_retention_days: _ignored, ...body } = values;
      void _ignored;
      write.mutate({ path: "calls/settings/", method: "PATCH", body }, { onSuccess: () => toast.success("Settings saved") });
    }}>
      <SectionCard title="Automatic SMS after a missed call" description="Sent by the phone that missed the call, through the normal SMS queue and its limits. Never to short codes, premium or blocked numbers, or customers who opted out.">
        <div className="grid gap-3">
          <label className="flex items-center gap-2 text-sm"><input disabled={disabled} type="checkbox" checked={values.auto_sms_enabled} onChange={(e) => set("auto_sms_enabled", e.target.checked)} />Send it</label>
          <label className="grid gap-1 text-sm"><span className="font-medium">Message ({"{company}"} is replaced)</span>
            <textarea disabled={disabled} rows={3} maxLength={300} value={values.auto_sms_template} onChange={(e) => set("auto_sms_template", e.target.value)} className="w-full rounded-lg border border-card-border bg-card-surface-area px-3 py-2 text-sm disabled:opacity-60" />
          </label>
          <label className="flex items-center gap-2 text-sm"><input disabled={disabled} type="checkbox" checked={values.auto_sms_after_hours_only} onChange={(e) => set("auto_sms_after_hours_only", e.target.checked)} />Only after office hours</label>
          <div className="grid gap-3 sm:grid-cols-2">
            {number("auto_sms_per_number_per_day", "At most per number per day", 1, 5)}
            {number("auto_sms_cooldown_hours", "Cool-down per number (hours)", 0, 168)}
          </div>
        </div>
      </SectionCard>
      <SectionCard title="Call-backs and notes">
        <div className="grid gap-3 sm:grid-cols-2">
          {number("unreturned_hours", "Unreturned after (hours)", 1, 168, "A missed call nobody returns within this time counts as unreturned.")}
          {number("callback_expiry_hours", "Call-back tasks expire after (hours)", 1, 720)}
          {number("outcome_required_after_seconds", "Outcome required after (seconds of talk, 0 = never)", 0, 36000)}
          <label className="flex items-center gap-2 self-end text-sm"><input disabled={disabled} type="checkbox" checked={values.post_call_card} onChange={(e) => set("post_call_card", e.target.checked)} />Show the post-call card on phones</label>
        </div>
      </SectionCard>
      <SectionCard title="Retention" description={`Calls older than this are deleted from the server (now ${values.effective_retention_days} days). Empty = the server default.`}>
        {number("retention_days", "Keep calls for (days, 0 = forever)", 0, 3650)}
      </SectionCard>
      {!disabled && <Button type="submit" isPending={write.isPending}>Save</Button>}
    </form>
  );
}
