"use client";

import { notFound, useParams } from "next/navigation";
import { Suspense } from "react";
import { ConversationListSkeleton } from "@/platforms/sms/components/inbox/conversation-list";
import { SmsWorkspace } from "@/platforms/sms/components/inbox/sms-workspace";
import { folderByKey } from "@/platforms/sms/folders";

export default function SmsFolderPage() {
  const { folder: key } = useParams<{ folder: string }>();
  const folder = folderByKey(key);
  if (!folder) notFound();
  return (
    <Suspense fallback={<ConversationListSkeleton />}>
      <SmsWorkspace folder={folder.key} title={folder.title} icon={folder.icon} empty={folder.empty} />
    </Suspense>
  );
}
