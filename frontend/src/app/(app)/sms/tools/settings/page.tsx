"use client";

import { usePageTitle } from "@/components/shell/trail";
import { Page, PageHeader } from "@/components/ui/page";
import { SmsNoticeCard, SmsServerSettings } from "@/platforms/sms/components/tools/settings-card";

export default function SmsSettingsPage() {
  usePageTitle({ page: "SMS settings", section: "Tools" });
  return (
    <Page>
      <PageHeader title="SMS settings" description="Platform-wide settings for the SMS platform. Per-phone options live on each phone's page." />
      <div className="space-y-4"><SmsNoticeCard /><SmsServerSettings /></div>
    </Page>
  );
}
