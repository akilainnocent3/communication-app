"use client";

import { notFound, useParams } from "next/navigation";
import { Suspense } from "react";
import { MailWorkspace } from "@/platforms/gmail/components/mail/mail-workspace";
import { ListSkeleton } from "@/platforms/gmail/components/mail/thread-list";
import { folderByKey } from "@/platforms/gmail/folders";

export default function FolderPage() {
  const { folder: key } = useParams<{ folder: string }>();
  const folder = folderByKey(key);
  if (!folder || !folder.label) notFound();
  return (
    <Suspense fallback={<ListSkeleton />}>
      <MailWorkspace title={folder.title} label={folder.label} icon={folder.icon} empty={folder.empty} />
    </Suspense>
  );
}
