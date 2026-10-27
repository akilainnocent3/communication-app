"use client";

import { OutboxPage } from "@/platforms/sms/components/outbox/outbox-list";

export default function SmsScheduledPage() {
  return <OutboxPage mode="scheduled" />;
}
