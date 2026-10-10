import { cn } from "@/utils/cn";

const TONES = {
  success: "bg-badge-success-background text-badge-success-text before:bg-success-500",
  warning: "bg-badge-warning-background text-badge-warning-text before:bg-warning-500",
  error: "bg-badge-error-background text-badge-error-text before:bg-error-500",
  info: "bg-badge-primary-background text-badge-primary-text before:bg-primary-500",
  neutral: "bg-badge-neutral-background text-badge-neutral-text before:bg-text-200",
} as const;

export type Tone = keyof typeof TONES;

/** Small status pill with a coloured dot (connected, syncing, needs reconnect…). */
export function StatusPill({ tone, children, pulse, className }: { tone: Tone; children: React.ReactNode; pulse?: boolean; className?: string }) {
  return (
    <span className={cn(
      "inline-flex h-6 shrink-0 items-center gap-1.5 rounded-full px-2.5 text-xs font-medium whitespace-nowrap before:size-1.5 before:rounded-full",
      pulse && "before:animate-pulse",
      TONES[tone], className,
    )}>
      {children}
    </span>
  );
}

/** Neutral chip (provider badge, counts). */
export function Chip({ children, className, style, title }: { children: React.ReactNode; className?: string; style?: React.CSSProperties; title?: string }) {
  return (
    <span title={title} style={style} className={cn("inline-flex h-5 shrink-0 items-center rounded-md bg-background-gray-secondary_alt px-1.5 text-[11px] font-medium whitespace-nowrap text-text-secondary", className)}>
      {children}
    </span>
  );
}
