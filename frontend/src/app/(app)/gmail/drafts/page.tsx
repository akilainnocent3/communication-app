"use client";

import { usePageTitle } from "@/components/shell/trail";
import { DraftsPage } from "@/platforms/gmail/components/outbox-lists";

export default function Page() {
  usePageTitle({ page: "Drafts", section: "Mail" });
  return <DraftsPage />;
}
