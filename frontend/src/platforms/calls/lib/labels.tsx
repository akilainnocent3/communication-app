import { CallIncomingIcon, CallMissedIcon, CallOutgoingIcon } from "@/components/ui/icons";
import type { Tone } from "@/components/ui/status-pill";
import { m } from "@/i18n";
import type { CallSummary } from "@/services/api/types";
import { cn } from "@/utils/cn";

export const MISSED = ["missed", "rejected", "voicemail"];

export function isMissed(call: Pick<CallSummary, "direction" | "result">) {
  return call.direction === "in" && MISSED.includes(call.result);
}

export function resultTone(call: Pick<CallSummary, "direction" | "result">): Tone {
  if (call.result === "answered") return "success";
  if (isMissed(call)) return "error";
  if (call.result === "blocked") return "neutral";
  return "warning";
}

export const resultLabel = (result: string) => m.calls.result[result] ?? result;

/** Direction glyph coloured by result (red missed, green answered, neutral otherwise). */
export function DirectionIcon({ call, size = 16, className }: { call: Pick<CallSummary, "direction" | "result">; size?: number; className?: string }) {
  const missed = isMissed(call);
  const Icon = missed ? CallMissedIcon : call.direction === "in" ? CallIncomingIcon : CallOutgoingIcon;
  const label = `${m.calls.direction[call.direction as "in" | "out"]}, ${resultLabel(call.result)}`;
  return (
    <span role="img" aria-label={label} title={label} className={cn("inline-flex shrink-0", missed ? "text-error-500" : call.result === "answered" ? "text-success-600 dark:text-success-400" : "text-text-tertiary", className)}>
      <Icon size={size} />
    </span>
  );
}

export function duration(seconds: number | null | undefined) {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}:${String(seconds % 60).padStart(2, "0")}`;
  return `${Math.floor(minutes / 60)}h ${String(minutes % 60).padStart(2, "0")}m`;
}

export function callTitle(call: Pick<CallSummary, "name" | "display_number" | "presentation">) {
  return call.name || call.display_number || m.calls.privateNumber;
}
