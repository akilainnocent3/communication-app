"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { useSession } from "@/components/shell/session-provider";
import { Button } from "@/components/tailgrids/core/button";
import { Field } from "@/components/ui/field";
import { TextAreaField } from "@/components/ui/form";
import { RequestState } from "@/components/ui/request-state";
import { SectionCard } from "@/components/ui/section-card";
import { errorMessage, mutate } from "@/services/api/client";
import type { SmsSettings } from "@/services/api/types";
import { smsKeys } from "../../api/keys";
import { useSmsSettings } from "../../api/queries";

/** The monitoring notice phone holders accept before enrolling (Settings → Integrations and SMS → Settings). */
export function SmsNoticeCard() {
  const settings = useSmsSettings();
  if (settings.isPending || settings.error) return <RequestState loading={settings.isPending} error={errorMessage(settings.error)} onRetry={() => settings.refetch()} />;
  return <NoticeForm data={settings.data!} />;
}

function NoticeForm({ data }: { data: SmsSettings }) {
  const client = useQueryClient();
  const { can } = useSession();
  const [notice, setNotice] = useState(data.monitoring_notice);
  const [signature, setSignature] = useState(data.default_signature);
  const [busy, setBusy] = useState(false);
  const canEdit = can("sms.manage_devices");
  const save = async () => {
    setBusy(true);
    try { client.setQueryData(smsKeys.settings(), await mutate<SmsSettings>("sms/settings/", "PUT", { monitoring_notice: notice, default_signature: signature })); toast.success("SMS settings saved."); }
    catch (error) { toast.error(errorMessage(error)); } finally { setBusy(false); }
  };
  return (
    <SectionCard title="SMS phone monitoring notice" description="Shown on the phone before it is enrolled; the holder must accept it, and the acceptance is stored with the phone. Supports the company's duties under Tanzania's Personal Data Protection Act. Intended for company-owned phones."
      footer={canEdit && <div className="flex justify-end"><Button onPress={save} isPending={busy} isDisabled={!notice.trim() || (notice === data.monitoring_notice && signature === data.default_signature)}>Save</Button></div>}>
      <div className="grid gap-4">
        <TextAreaField label="Notice" value={notice} onChange={(e) => setNotice(e.target.value)} rows={4} maxLength={2000} disabled={!canEdit} />
        <Field label="Suggested admin signature" value={signature} onChange={setSignature} maxLength={40} isDisabled={!canEdit} hint="Offered when enrolling a phone. Plain characters keep messages at 160 per SMS." />
      </div>
    </SectionCard>
  );
}

export function SmsServerSettings() {
  const settings = useSmsSettings();
  const data = settings.data;
  if (!data) return null;
  const rows: [string, string][] = [
    ["Keep messages on the server", data.retention_days ? `${data.retention_days} days` : "Forever"],
    ["Deletions on the phone", data.mirror_device_deletes ? "Also delete the server copy" : "Keep the server copy (shown as “Deleted on phone”)"],
    ["Unsent admin messages expire after", `${data.outbound_ttl_hours} hours`],
    ["Daily limit per phone", `${data.daily_cap} messages from the admin`],
    ["Short codes", data.allow_short_codes ? "Allowed" : "Refused (can be premium-rate)"],
    ["Instant wake-ups (Firebase)", data.push_configured ? "Configured" : "Not configured: phones poll every 20 s"],
  ];
  return (
    <SectionCard title="Server policy" description="Set by environment variables on the server (docs/deployment.md).">
      <dl className="divide-y divide-card-border">
        {rows.map(([label, value]) => <div key={label} className="flex justify-between gap-3 py-2 text-sm"><dt className="text-text-tertiary">{label}</dt><dd className="text-right text-text-primary">{value}</dd></div>)}
      </dl>
    </SectionCard>
  );
}
