import { useId } from "react";
import { cn } from "@/utils/cn";
import { m } from "@/i18n";

/** Communication Manager mark: a speech bubble whose tail forms an envelope fold (every channel, one place). */
export function BrandMark({ size = 32, className }: { size?: number; className?: string }) {
  // Unique per instance: a shared id resolves to the first copy, which may sit in a hidden (display:none) sidebar.
  const gradient = `cm-mark-${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" role="img" aria-label={m.brand.name} className={cn("shrink-0", className)}>
      <defs>
        <linearGradient id={gradient} x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop stopColor="#5e84fc" />
          <stop offset="1" stopColor="#2237ee" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill={`url(#${gradient})`} />
      <path d="M8 10.5A2.5 2.5 0 0 1 10.5 8h11A2.5 2.5 0 0 1 24 10.5v7a2.5 2.5 0 0 1-2.5 2.5H15l-4.2 3.6c-.5.4-1.3.1-1.3-.6V20h0A1.5 1.5 0 0 1 8 18.5z" fill="white" />
      <path d="m10.5 11 5.5 4 5.5-4" fill="none" stroke="#3758f9" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function BrandLogo({ size = 32, className }: { size?: number; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <BrandMark size={size} />
      <span className="flex flex-col leading-none">
        <span className="text-[15px] font-semibold tracking-tight text-text-primary">Communication</span>
        <span className="mt-0.5 text-[11px] font-medium tracking-[0.18em] text-text-tertiary uppercase">Manager</span>
      </span>
    </span>
  );
}
