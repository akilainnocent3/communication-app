import type { ReactNode } from "react";
import { cn } from "@/utils/cn";

const PADDING = { none: "", sm: "p-3 sm:p-4", md: "p-4 sm:p-5" };
const TONE = {
  default: "border-card-border bg-card-surface-area",
  muted: "border-card-border bg-background-gray-secondary_alt/40",
  danger: "border-error-300 bg-error-50/40 dark:border-error-500/40 dark:bg-error-500/10",
};

/** Card surface classes, for markup that cannot use `SectionCard` itself (list items, `<details>`…). */
export function cardClass({ padding = "md", tone = "default", interactive = false }: {
  padding?: keyof typeof PADDING;
  tone?: keyof typeof TONE;
  interactive?: boolean;
} = {}) {
  return cn(
    "min-w-0 rounded-xl border text-text-primary",
    TONE[tone],
    PADDING[padding],
    interactive && "transition-colors hover:border-primary-400 focus-within:ring-2 focus-within:ring-primary-500/40",
  );
}

/** Shared feature section: consistent padding, radius, border and dark-mode surface. */
export function SectionCard({
  title,
  description,
  actions,
  children,
  footer,
  className,
  bodyClassName,
  padding = "md",
  tone = "default",
  interactive = false,
  as: Tag = "section",
  ...rest
}: {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
  /** Bottom bar separated by a border (form buttons, totals). */
  footer?: ReactNode;
  className?: string;
  bodyClassName?: string;
  padding?: keyof typeof PADDING;
  tone?: keyof typeof TONE;
  /** Hover border and focus ring for cards that contain one main action. */
  interactive?: boolean;
  as?: "section" | "div" | "aside" | "article" | "li" | "form";
  id?: string;
  role?: string;
  "aria-label"?: string;
  "aria-labelledby"?: string;
}) {
  const header = title || description || actions;
  return (
    <Tag className={cn(cardClass({ padding, tone, interactive }), className)} {...rest}>
      {header && (
        <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            {title && <h2 className="font-semibold text-text-primary">{title}</h2>}
            {description && <p className="mt-0.5 text-sm text-text-tertiary">{description}</p>}
          </div>
          {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
        </div>
      )}
      <div className={bodyClassName}>{children}</div>
      {footer && <div className="mt-4 border-t border-card-border pt-3">{footer}</div>}
    </Tag>
  );
}

const STAT_BAR = { success: "before:bg-success-500", warning: "before:bg-warning-500", error: "before:bg-error-500" };

/** One KPI figure: label, value and an optional hint; `tone` adds a coloured edge. */
export function StatCard({ label, value, hint, icon, tone, title, className, style, as: Tag = "div" }: {
  label: ReactNode;
  value: ReactNode;
  hint?: ReactNode;
  icon?: ReactNode;
  tone?: keyof typeof STAT_BAR;
  /** Full value for a tooltip when `value` is abbreviated. */
  title?: string;
  className?: string;
  style?: React.CSSProperties;
  as?: "div" | "li";
}) {
  return (
    <Tag
      style={style}
      className={cn(
        "group relative min-w-0 overflow-hidden rounded-xl border border-card-border bg-card-surface-area p-3 transition-colors hover:border-primary-500/30 hover:bg-linear-to-br hover:from-primary-500/5 hover:to-transparent sm:p-4",
        tone && `before:absolute before:inset-y-0 before:left-0 before:w-1 ${STAT_BAR[tone]}`,
        className,
      )}
    >
      <dt className="flex items-center gap-1.5 text-xs font-medium text-text-tertiary">
        {icon && <span className="shrink-0 text-icon-tertiary" aria-hidden="true">{icon}</span>}
        <span className="truncate">{label}</span>
      </dt>
      <dd className="mt-1.5 text-base font-semibold break-words tabular-nums text-text-primary sm:text-lg xl:text-xl" title={title}>{value}</dd>
      {hint && <dd className="mt-0.5 text-xs text-text-tertiary">{hint}</dd>}
    </Tag>
  );
}
