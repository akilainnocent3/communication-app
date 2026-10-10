"use client";

import type { ReactNode } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { BrandMark } from "@/components/shell/brand";
import { SessionProvider, useSession } from "@/components/shell/session-provider";
import { ActivityIndicator } from "@/components/ui/activity-indicator";
import { RequestState } from "@/components/ui/request-state";
import { useQueryClient } from "@tanstack/react-query";
import { ME_KEY } from "@/components/shell/session-provider";

function Gate({ children }: { children: ReactNode }) {
  const { me } = useSession();
  const client = useQueryClient();
  const state = client.getQueryState(ME_KEY);
  if (!me) {
    const failed = state?.status === "error" && (state.error as { status?: number } | null)?.status !== 401;
    return (
      <div className="flex h-full flex-col items-center justify-center gap-5 bg-card-surface-area px-6">
        <BrandMark size={44} className="animate-pulse" />
        {failed ? (
          <div className="w-full max-w-md"><RequestState loading={false} error="Couldn't load your workspace. Check your connection and try again." onRetry={() => client.refetchQueries({ queryKey: ME_KEY })} /></div>
        ) : (
          <ActivityIndicator label="Loading your workspace" />
        )}
      </div>
    );
  }
  return <AppShell>{children}</AppShell>;
}

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <SessionProvider>
      <Gate>{children}</Gate>
    </SessionProvider>
  );
}
