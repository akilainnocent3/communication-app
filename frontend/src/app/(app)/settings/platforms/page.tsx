"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { ME_KEY, useSession } from "@/components/shell/session-provider";
import { usePageTitle } from "@/components/shell/trail";
import { Button } from "@/components/tailgrids/core/button";
import { SwitchRow } from "@/components/ui/form";
import { ChevronDownIcon, ChevronUpIcon } from "@/components/ui/icons";
import { Page, PageHeader } from "@/components/ui/page";
import { RequestState } from "@/components/ui/request-state";
import { SectionCard } from "@/components/ui/section-card";
import { Chip } from "@/components/ui/status-pill";
import { errorMessage, mutate, request } from "@/services/api/client";
import type { Platform } from "@/services/api/types";
import { PLATFORMS } from "@/platforms/registry";

const KEY = ["settings", "platforms"] as const;

export default function PlatformsPage() {
  usePageTitle({ page: "Platforms", section: "Settings" });
  const { isSuperAdmin } = useSession();
  const client = useQueryClient();
  const platforms = useQuery({ queryKey: KEY, queryFn: () => request<Platform[]>("settings/platforms/"), enabled: isSuperAdmin });
  const [draft, setDraft] = useState<Platform[] | null>(null);
  const [busy, setBusy] = useState(false);
  const rows = draft ?? [...(platforms.data ?? [])].sort((a, b) => a.order - b.order);

  if (!isSuperAdmin) return <Page><PageHeader title="Platforms" description="Only a super admin can turn platforms on or off." /></Page>;

  const move = (index: number, delta: number) => {
    const next = [...rows];
    const [item] = next.splice(index, 1);
    next.splice(index + delta, 0, item);
    setDraft(next.map((p, i) => ({ ...p, order: i * 10 })));
  };
  const save = async () => {
    setBusy(true);
    try {
      const data = await mutate<Platform[]>("settings/platforms/", "PUT", rows.map(({ key, is_enabled, order }) => ({ key, is_enabled, order })));
      client.setQueryData(KEY, data); setDraft(null);
      client.invalidateQueries({ queryKey: ME_KEY });
      toast.success("Platforms updated.");
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };

  const comingSoon = PLATFORMS.filter((p) => p.status === "coming_soon");
  return (
    <Page className="max-w-3xl">
      <PageHeader title="Platforms" description="Communication channels available in the workspace. Order sets their place in the switcher." />
      {platforms.isPending || platforms.error ? <RequestState loading={platforms.isPending} error={errorMessage(platforms.error)} onRetry={() => platforms.refetch()} /> : (
        <SectionCard footer={draft && <div className="flex justify-end gap-2"><Button appearance="outline" onPress={() => setDraft(null)}>Discard</Button><Button onPress={save} isPending={busy}>Save</Button></div>}>
          <ul className="divide-y divide-card-border">
            {rows.map((platform, index) => {
              const def = PLATFORMS.find((p) => p.key === platform.key);
              return (
                <li key={platform.key} className="flex items-center gap-3">
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary-500/10 text-primary-500 [&_svg]:size-5" aria-hidden="true">{def?.icon}</span>
                  <div className="min-w-0 flex-1">
                    <SwitchRow title={platform.name} description={`${def?.description ?? ""} · needs ${platform.permission}`} checked={platform.is_enabled}
                      onChange={(is_enabled) => setDraft(rows.map((p) => (p.key === platform.key ? { ...p, is_enabled } : p)))} />
                  </div>
                  <div className="flex flex-col">
                    <Button size="sm" appearance="ghost" iconOnly aria-label={`Move ${platform.name} up`} isDisabled={index === 0} onPress={() => move(index, -1)}><ChevronUpIcon /></Button>
                    <Button size="sm" appearance="ghost" iconOnly aria-label={`Move ${platform.name} down`} isDisabled={index === rows.length - 1} onPress={() => move(index, 1)}><ChevronDownIcon /></Button>
                  </div>
                </li>
              );
            })}
          </ul>
          {comingSoon.length > 0 && (
            <div className="mt-4 border-t border-card-border pt-4">
              <p className="mb-2 text-xs font-semibold tracking-wide text-text-tertiary uppercase">Coming soon</p>
              <ul className="flex flex-wrap gap-2">{comingSoon.map((p) => <li key={p.key}><Chip className="h-7 gap-1.5 px-2.5 [&_svg]:size-4">{p.icon}{p.name}</Chip></li>)}</ul>
            </div>
          )}
        </SectionCard>
      )}
    </Page>
  );
}
