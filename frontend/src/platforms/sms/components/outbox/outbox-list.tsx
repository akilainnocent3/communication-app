"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/tailgrids/core/button";
import { EmptyState } from "@/components/ui/empty-state";
import { OutboxIcon } from "@/components/ui/icons";
import { Page, PageHeader } from "@/components/ui/page";
import { RequestState } from "@/components/ui/request-state";
import { cardClass } from "@/components/ui/section-card";
import { StatusPill, type Tone } from "@/components/ui/status-pill";
import { usePageTitle } from "@/components/shell/trail";
import { m } from "@/i18n";
import { dateTime } from "@/lib/format";
import { errorMessage, mutate } from "@/services/api/client";
import type { OutboxItem } from "@/services/api/types";
import { cn } from "@/utils/cn";
import { useDeviceScope, useDeviceSummaries, useOutbox } from "../../api/queries";
import { statusLabel } from "../chat/message-bubble";

const TONE: Record<string, Tone> = { queued: "neutral", dispatched: "info", sending: "info", failed: "error", expired: "error", unknown: "warning" };

function Row({ item, onChanged }: { item: OutboxItem; onChanged: () => void }) {
  const devices = useDeviceSummaries();
  const canSend = !!devices.find((device) => device.id === item.device.id)?.permissions.send;
  const run = async (path: "cancel" | "retry") => {
    try { await mutate(`sms/messages/${item.id}/${path}/`, "POST"); toast.success(path === "cancel" ? m.sms.composer.undone : m.sms.composer.sent); onChanged(); }
    catch (error) { toast.error(errorMessage(error)); }
  };
  const device = devices.find((d) => d.id === item.device.id);
  return (
    <li className={cn(cardClass({ padding: "sm" }), "flex flex-wrap items-start gap-3")} data-outbox-item={item.id}>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <Link href={`/sms/inbox?c=${item.conversation}`} className="font-semibold text-text-primary hover:underline">{item.conversation_title}</Link>
          <StatusPill tone={TONE[item.status] ?? "neutral"} pulse={item.status === "sending"}>{statusLabel(item.status)}</StatusPill>
          <span className="text-xs text-text-tertiary"><span style={{ color: item.device.colour }}>●</span> {item.device.name}</span>
        </div>
        <p className="mt-1 line-clamp-2 text-sm text-text-secondary">{item.body}</p>
        <p className="mt-1 text-xs text-text-tertiary">
          {item.sent_by ? `${item.sent_by.display_name} · ` : ""}{item.is_scheduled && item.status === "queued" ? `Scheduled for ${dateTime(item.send_at ?? item.at)}` : dateTime(item.at)}
          {item.status === "queued" && device && !device.online && ` · ${m.sms.chat.waiting(device.name)}`}
          {item.error_detail && ` · ${item.error_detail}`}
        </p>
      </div>
      {canSend && (
        <div className="flex shrink-0 gap-2">
          {item.status === "queued" && <Button size="sm" appearance="outline" onPress={() => run("cancel")}>{m.sms.chat.cancel}</Button>}
          {["failed", "expired", "unknown"].includes(item.status) && <Button size="sm" onPress={() => run("retry")}>{m.sms.chat.retry}</Button>}
        </div>
      )}
    </li>
  );
}

/** Outbox (on its way / needs a decision) and Scheduled share this list. */
export function OutboxPage({ mode }: { mode: "outbox" | "scheduled" }) {
  usePageTitle({ page: mode === "outbox" ? "Outbox" : "Scheduled", section: "Messages" });
  const [scope] = useDeviceScope();
  const [tab, setTab] = useState<"pending" | "problems">("pending");
  const view = mode === "scheduled" ? "scheduled" : tab;
  const client = useQueryClient();
  const list = useOutbox(view, scope);
  const refresh = () => client.invalidateQueries({ queryKey: ["sms", "outbox"] });
  return (
    <Page wide key={scope}>
      <PageHeader title={mode === "outbox" ? "Outbox" : "Scheduled"} description={mode === "outbox"
        ? "Messages from the admin that a phone has not sent yet, and messages that need a decision."
        : "Messages that will be sent later. Cancel any of them until the phone picks them up."} />
      {mode === "outbox" && (
        <div role="tablist" aria-label="Outbox" className="mb-4 inline-flex rounded-lg border border-card-border bg-card-surface-area p-0.5">
          {(["pending", "problems"] as const).map((key) => (
            <button key={key} type="button" role="tab" aria-selected={tab === key} onClick={() => setTab(key)}
              className={cn("h-8 rounded-md px-3 text-sm font-medium", tab === key ? "bg-primary-500 text-white" : "text-text-secondary hover:text-text-primary")}>
              {key === "pending" ? "On its way" : "Needs attention"}
            </button>
          ))}
        </div>
      )}
      {list.isPending || list.error ? <RequestState loading={list.isPending} error={errorMessage(list.error)} onRetry={() => list.refetch()} variant="table" /> : list.data!.length === 0 ? (
        <div className={cardClass()}><EmptyState icon={<OutboxIcon />} title={view === "problems" ? "Nothing needs attention" : view === "scheduled" ? "Nothing scheduled" : "The outbox is empty"}
          body={view === "scheduled" ? "Use Schedule send in the composer to send later." : "Every message from the admin has been handed to its phone."} /></div>
      ) : (
        <ul className="space-y-2">{list.data!.map((item) => <Row key={item.id} item={item} onChanged={refresh} />)}</ul>
      )}
    </Page>
  );
}
