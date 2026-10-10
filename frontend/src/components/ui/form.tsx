"use client";

import { useId, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { cn } from "@/utils/cn";

/** Same look as the TailGrids input, for native elements (select, textarea, date-time). */
export const controlClass =
  "w-full max-w-full rounded-lg border border-card-border bg-input-background px-3.5 py-2.5 text-sm text-text-primary duration-200 outline-none focus:border-input-primary-focus-border focus:ring-4 focus:ring-input-primary-focus-border/20 disabled:cursor-not-allowed disabled:opacity-60 aria-invalid:border-input-error-focus-border";

function Wrapper({ id, label, hint, error, children, className }: { id: string; label: ReactNode; hint?: ReactNode; error?: string; children: ReactNode; className?: string }) {
  return (
    <div className={cn("flex min-w-0 flex-col gap-2 text-sm", className)}>
      <label htmlFor={id} className="font-medium text-text-primary">{label}</label>
      {children}
      {hint && !error && <p id={`${id}-hint`} className="text-xs text-text-tertiary">{hint}</p>}
      {error && <p id={`${id}-error`} className="text-xs text-error-500">{error}</p>}
    </div>
  );
}

/** Native <select> (best on phones) with a label, hint and error. */
export function SelectField({ label, hint, error, options, className, ...props }: SelectHTMLAttributes<HTMLSelectElement> & {
  label: ReactNode; hint?: ReactNode; error?: string; options: { value: string | number; label: string; disabled?: boolean }[];
}) {
  const id = useId();
  return (
    <Wrapper id={id} label={label} hint={hint} error={error} className={className}>
      <select id={id} aria-invalid={!!error || undefined} aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined} className={cn(controlClass, "h-10.5 py-0 pr-8")} {...props}>
        {options.map((option) => <option key={option.value} value={option.value} disabled={option.disabled}>{option.label}</option>)}
      </select>
    </Wrapper>
  );
}

export function TextAreaField({ label, hint, error, className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement> & { label: ReactNode; hint?: ReactNode; error?: string }) {
  const id = useId();
  return (
    <Wrapper id={id} label={label} hint={hint} error={error} className={className}>
      <textarea id={id} aria-invalid={!!error || undefined} aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined} className={cn(controlClass, "min-h-24 leading-relaxed")} {...props} />
    </Wrapper>
  );
}

/** A labelled switch row: title, one-line description and the toggle on the right. */
export function SwitchRow({ title, description, checked, onChange, disabled }: {
  title: ReactNode; description?: ReactNode; checked: boolean; onChange: (checked: boolean) => void; disabled?: boolean;
}) {
  const id = useId();
  return (
    <div className="flex items-start justify-between gap-4 py-3">
      <div className="min-w-0">
        <label htmlFor={id} className="text-sm font-medium text-text-primary">{title}</label>
        {description && <p id={`${id}-desc`} className="mt-0.5 text-xs text-text-tertiary">{description}</p>}
      </div>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        aria-describedby={description ? `${id}-desc` : undefined}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative mt-0.5 inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2 focus-visible:outline-none disabled:opacity-50",
          checked ? "bg-primary-500" : "bg-text-200/60 dark:bg-white/15",
        )}
      >
        <span className={cn("inline-block size-5 rounded-full bg-white shadow-sm transition-transform", checked ? "translate-x-5.5" : "translate-x-0.5")} />
      </button>
    </div>
  );
}

/** A colour swatch picker (office / label / mailbox colours). */
export const SWATCHES = ["#3758f9", "#0ea5e9", "#14b8a6", "#22c55e", "#eab308", "#f97316", "#ef4444", "#ec4899", "#8b5cf6", "#64748b"];

export function ColourPicker({ label, value, onChange }: { label: string; value: string; onChange: (colour: string) => void }) {
  return (
    <fieldset className="min-w-0 text-sm">
      <legend className="mb-2 font-medium text-text-primary">{label}</legend>
      <div className="flex flex-wrap gap-2" role="radiogroup" aria-label={label}>
        {SWATCHES.map((colour) => (
          <button
            key={colour}
            type="button"
            role="radio"
            aria-checked={value.toLowerCase() === colour}
            aria-label={colour}
            onClick={() => onChange(colour)}
            className={cn(
              "size-7 rounded-full border-2 border-transparent transition focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:outline-none",
              value.toLowerCase() === colour && "border-card-surface-area ring-2 ring-text-primary",
            )}
            style={{ background: colour }}
          />
        ))}
      </div>
    </fieldset>
  );
}
