"use client";

import Link from "next/link";
import type { ComponentProps } from "react";
import { cn } from "@/utils/cn";
import { buttonStyles, type ButtonProps } from "./button";

export type ButtonLinkProps = ComponentProps<typeof Link> &
  Pick<ButtonProps, "variant" | "appearance" | "iconOnly" | "size">;

/**
 * Navigation that looks like a button. It stays a real link (href, new tab, prefetch) and reuses the shared
 * `buttonStyles`, so pages never hand-copy button classes onto `<Link>`.
 */
export function ButtonLink({ variant, appearance, iconOnly, size, className, ...props }: ButtonLinkProps) {
  let normalizedVariant = variant;
  let normalizedAppearance = appearance;
  if (variant === "ghost") {
    normalizedVariant = "primary";
    normalizedAppearance = "ghost";
  }
  return (
    <Link
      className={cn(
        buttonStyles({ variant: normalizedVariant, appearance: normalizedAppearance, iconOnly, size }),
        "focus-visible:ring-4",
        className,
      )}
      {...props}
    />
  );
}
