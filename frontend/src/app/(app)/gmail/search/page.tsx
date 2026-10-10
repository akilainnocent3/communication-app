"use client";

import { Suspense } from "react";
import { SearchIcon } from "@/components/ui/icons";
import { MailWorkspace } from "@/platforms/gmail/components/mail/mail-workspace";
import { ListSkeleton } from "@/platforms/gmail/components/mail/thread-list";

export default function SearchPage() {
  return (
    <Suspense fallback={<ListSkeleton />}>
      <MailWorkspace title="search results" search icon={<SearchIcon />} empty={{ title: "No results", body: "" }} />
    </Suspense>
  );
}
