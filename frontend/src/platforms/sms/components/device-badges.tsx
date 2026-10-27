import { StatusPill } from "@/components/ui/status-pill";
import { m } from "@/i18n";
import { ago, initials } from "@/lib/format";
import { cn } from "@/utils/cn";

/** Office-coloured initials with an online dot. */
export function DeviceAvatar({ name, colour, online, size = 28, className }: { name: string; colour: string; online?: boolean; size?: number; className?: string }) {
  return (
    <span aria-hidden="true" className={cn("relative flex shrink-0 items-center justify-center rounded-full font-semibold text-white", className)}
      style={{ width: size, height: size, background: colour || "#10b981", fontSize: Math.max(10, size * 0.36) }}>
      {initials(name)}
      {online !== undefined && (
        <span className={cn("absolute -right-0.5 -bottom-0.5 size-2.5 rounded-full ring-2 ring-card-surface-area", online ? "bg-success-500" : "bg-text-200")} />
      )}
    </span>
  );
}

export function OnlineLabel({ online, lastSeen, className }: { online: boolean; lastSeen: string | null | undefined; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5", className)}>
      <span aria-hidden="true" className={cn("size-2 rounded-full", online ? "bg-success-500" : "bg-text-200")} />
      {online ? m.sms.online : lastSeen ? m.sms.lastSeen(ago(lastSeen)) : m.sms.neverSeen}
    </span>
  );
}

export function DeviceStatusPill({ status, online }: { status: string; online: boolean }) {
  if (status === "revoked") return <StatusPill tone="neutral">{m.sms.devices.status.revoked}</StatusPill>;
  if (status === "suspended") return <StatusPill tone="warning">{m.sms.devices.status.suspended}</StatusPill>;
  return online ? <StatusPill tone="success">{m.sms.online}</StatusPill> : <StatusPill tone="neutral">{m.sms.offline}</StatusPill>;
}

export function attentionLabel(code: string): string {
  return (m.sms.attention as Record<string, string>)[code] ?? code;
}
