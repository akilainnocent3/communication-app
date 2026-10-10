"use client";

import { useParams } from "next/navigation";
import { Suspense } from "react";
import { usePageTitle } from "@/components/shell/trail";
import { TagIcon } from "@/components/ui/icons";
import { useLabels, useMailboxScope } from "@/platforms/gmail/api/queries";
import { MailWorkspace } from "@/platforms/gmail/components/mail/mail-workspace";
import { ListSkeleton } from "@/platforms/gmail/components/mail/thread-list";

export default function LabelPage() {
  const { labelId } = useParams<{ labelId: string }>();
  const id = decodeURIComponent(labelId);
  const [scope] = useMailboxScope();
  const labels = useLabels(scope === "all" ? undefined : scope);
  const label = labels.data?.find((item) => item.label_id === id);
  const name = label?.name ?? "Label";
  usePageTitle({ page: name, section: "Labels" });
  return (
    <Suspense fallback={<ListSkeleton />}>
      <MailWorkspace title={name} label={id} icon={<TagIcon />} empty={{ title: `Nothing labelled “${name}”`, body: "Conversations with this label appear here. Select conversations and press l to label them." }} />
    </Suspense>
  );
}
