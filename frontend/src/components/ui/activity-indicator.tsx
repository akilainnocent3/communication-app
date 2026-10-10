import { cn } from "@/utils/cn";

/** Diameter in px (Flutter AppActivityIndicator radius 10 ≈ "md"). */
const SIZES = { xs: 14, sm: 16, md: 22, lg: 34 } as const;
const SPOKES = 12;

/**
 * Next.js twin of the mobile app's `AppActivityIndicator` (CupertinoActivityIndicator): twelve rounded spokes in a
 * circle, each fading one twelfth of a second after the previous. It takes the current text colour, so it follows the
 * light/dark tokens. With reduced motion the spokes stay still at graded opacity.
 *
 * `decorative` hides it from assistive technology when the surrounding control already announces the busy state
 * (a pending button sets `aria-busy`).
 */
export function ActivityIndicator({ size = "md", label = "Loading", decorative = false, className }: {
  size?: keyof typeof SIZES;
  label?: string;
  decorative?: boolean;
  className?: string;
}) {
  const diameter = SIZES[size];
  const width = Math.max(1.5, diameter * 0.09);
  const height = diameter * 0.28;
  const spokes = (
    <span aria-hidden className="relative inline-block shrink-0" style={{ width: diameter, height: diameter }} data-activity-indicator="">
      {Array.from({ length: SPOKES }, (_, index) => (
        <span
          key={index}
          className="cm-activity-spoke absolute top-0 rounded-full bg-current"
          style={{
            left: (diameter - width) / 2,
            width,
            height,
            transformOrigin: `50% ${diameter / 2}px`,
            transform: `rotate(${index * (360 / SPOKES)}deg)`,
            animationDelay: `${(index - SPOKES) / SPOKES}s`,
            opacity: 1 - (index * 0.85) / SPOKES,
          }}
        />
      ))}
    </span>
  );
  if (decorative) return <span className={cn("inline-flex text-current", className)}>{spokes}</span>;
  return (
    <span role="status" aria-live="polite" className={cn("inline-flex items-center text-text-tertiary", className)}>
      {spokes}
      <span className="sr-only">{label}</span>
    </span>
  );
}

/** Centered page/section loading state. */
export function LoadingBlock({ label = "Loading", className }: { label?: string; className?: string }) {
  return (
    <div className={cn("flex min-h-32 items-center justify-center py-8", className)}>
      <ActivityIndicator size="lg" label={label} />
    </div>
  );
}
