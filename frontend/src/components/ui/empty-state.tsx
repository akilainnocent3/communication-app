import type { ReactNode } from "react";
import { cn } from "@/utils/cn";

/** Friendly empty state: soft illustration, a title, one sentence and the next action. */
export function EmptyState({ icon, title, body, action, className, compact = false }: {
  icon?: ReactNode; title: ReactNode; body?: ReactNode; action?: ReactNode; className?: string; compact?: boolean;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center px-6 text-center", compact ? "py-10" : "py-16 sm:py-20", className)}>
      <div aria-hidden="true" className="relative mb-5">
        <div className="absolute inset-0 -m-3 rounded-full bg-primary-500/8 blur-md" />
        <div className="relative flex size-16 items-center justify-center rounded-2xl border border-card-border bg-linear-to-br from-primary-500/10 to-transparent text-primary-500 shadow-xs dark:text-primary-300 [&_svg]:size-7">
          {icon}
        </div>
      </div>
      <h2 className="text-base font-semibold text-text-primary">{title}</h2>
      {body && <p className="mt-1.5 max-w-sm text-sm text-text-tertiary">{body}</p>}
      {action && <div className="mt-5 flex flex-wrap justify-center gap-2">{action}</div>}
    </div>
  );
}
