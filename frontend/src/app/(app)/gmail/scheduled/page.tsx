"use client";

import { usePageTitle } from "@/components/shell/trail";
import { ScheduledPage } from "@/platforms/gmail/components/outbox-lists";

export default function Page() {
  usePageTitle({ page: "Scheduled", section: "Mail" });
  return <ScheduledPage />;
}
