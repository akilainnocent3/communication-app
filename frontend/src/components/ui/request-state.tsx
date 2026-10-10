"use client";
import { Button } from "@/components/tailgrids/core/button";
import { Skeleton } from "@/components/tailgrids/core/skeleton";
import { LoadingBlock } from "./activity-indicator";

/** Placeholder rows shaped like a DataTable while its first page loads. */
export function TableSkeleton({ rows = 6, columns = 5 }: { rows?: number; columns?: number }) {
  return (
    <div role="status" aria-label="Loading" className="overflow-hidden rounded-xl border border-card-border bg-card-surface-area p-3">
      <span className="sr-only">Loading…</span>
      <div className="mb-4 h-4 w-40"><Skeleton className="h-4 w-40" /></div>
      <div className="divide-y divide-card-border">
        {Array.from({ length: rows }, (_, row) => (
          <div key={row} className="grid gap-4 px-2 py-3.5" style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}>
            {Array.from({ length: columns }, (_, column) => (
              <Skeleton key={column} className={column === 0 ? "h-3.5 w-4/5" : "h-3.5 w-3/5"} />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

export function RequestState({ loading, error, onRetry, variant = "block" }: {
  loading: boolean;
  error?: string;
  onRetry: () => void | Promise<unknown>;
  /** "table" shows skeleton rows instead of a spinner. */
  variant?: "block" | "table";
}) {
  if (loading) return variant === "table" ? <TableSkeleton /> : <LoadingBlock />;
  if (error) return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-error-500/30 bg-error-500/5 p-4">
      <p role="alert" className="text-sm text-text-primary">{error}</p>
      <Button appearance="outline" onPress={onRetry}>Retry</Button>
    </div>
  );
  return null;
}

/** In-content placeholder shaped like a typical page (title, two lines, four cards, a table); the shell stays put. */
export function PageSkeleton({ className, ...props }: { className?: string; "data-route-loading"?: string }) {
  return (
    <div role="status" aria-label="Loading page" className={className} {...props}>
      <span className="sr-only">Loading page…</span>
      <div className="space-y-2.5">
        <Skeleton className="h-2.5 w-40" />
        <Skeleton className="h-6 w-64 max-w-[70%]" />
        <Skeleton className="h-3 w-80 max-w-[85%]" />
      </div>
      <div className="mt-5 grid grid-cols-2 gap-2 sm:gap-3 md:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <div key={index} className="space-y-3 rounded-xl border border-card-border bg-card-surface-area p-3 sm:p-4">
            <Skeleton className="h-2.5 w-2/3" />
            <Skeleton className="h-4 w-1/2" />
          </div>
        ))}
      </div>
      <div className="mt-5"><TableSkeleton rows={5} /></div>
    </div>
  );
}
