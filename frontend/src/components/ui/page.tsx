import type { ReactNode } from "react";
import { cn } from "@/utils/cn";

/** Standard page wrapper: gutter, max width and the fade-up entrance used by every non-mail page. */
export function Page({ children, className, wide = false }: { children: ReactNode; className?: string; wide?: boolean }) {
  return <div className={cn("mx-auto w-full animate-fade-up px-4 pt-5 pb-10 sm:px-6 lg:pt-6", wide ? "max-w-384" : "max-w-6xl", className)}>{children}</div>;
}

export function PageHeader({ title, description, actions, eyebrow }: { title: ReactNode; description?: ReactNode; actions?: ReactNode; eyebrow?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3 sm:mb-6">
      <div className="min-w-0">
        {eyebrow && <p className="mb-1 text-xs font-semibold tracking-[0.14em] text-primary-500 uppercase dark:text-primary-300">{eyebrow}</p>}
        <h1 className="text-xl font-semibold tracking-tight text-text-primary sm:text-2xl">{title}</h1>
        {description && <p className="mt-1 max-w-2xl text-sm text-text-tertiary">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
