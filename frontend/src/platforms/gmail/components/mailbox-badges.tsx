import { Chip, StatusPill } from "@/components/ui/status-pill";
import type { MailboxStatusName } from "@/services/api/types";
import { initials } from "@/lib/format";
import { cn } from "@/utils/cn";

export function MailboxAvatar({ name, colour, size = 28, className }: { name: string; colour: string; size?: number; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn("flex shrink-0 items-center justify-center rounded-full font-semibold text-white", className)}
      style={{ width: size, height: size, background: colour || "#3758f9", fontSize: Math.max(10, size * 0.38) }}
    >
      {initials(name)}
    </span>
  );
}

export const PROVIDER_LABEL: Record<string, string> = {
  gmail_oauth: "Google", workspace_delegation: "Workspace", imap_smtp: "IMAP", fake: "Demo",
};

export function ProviderBadge({ provider }: { provider: string }) {
  return <Chip>{PROVIDER_LABEL[provider] ?? provider}</Chip>;
}

export function MailboxStatus({ status, progress }: { status: MailboxStatusName | string; progress?: { done?: number; total?: number } | unknown }) {
  const p = (progress ?? {}) as { done?: number; total?: number };
  switch (status) {
    case "connected": return <StatusPill tone="success">Connected</StatusPill>;
    case "syncing": {
      const pct = p.total ? Math.min(100, Math.round(((p.done ?? 0) / p.total) * 100)) : null;
      return <StatusPill tone="info" pulse>{pct === null ? "Syncing" : `Syncing ${pct}%`}</StatusPill>;
    }
    case "needs_reconnect": return <StatusPill tone="warning">Needs reconnect</StatusPill>;
    case "error": return <StatusPill tone="error">Error</StatusPill>;
    case "disabled": return <StatusPill tone="neutral">Disconnected</StatusPill>;
    default: return <StatusPill tone="neutral">Waiting to connect</StatusPill>;
  }
}
