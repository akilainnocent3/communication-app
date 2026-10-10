"use client";

import { ActivityIndicator } from "@/components/ui/activity-indicator";
import { cn } from "@/utils/cn";
import { cva } from "class-variance-authority";
import { useEffect, useImperativeHandle, useRef, useState, type Ref } from "react";
import {
  Button as RACButton,
  type ButtonProps as RACButtonProps,
  type PressEvent,
  composeRenderProps,
} from "react-aria-components";

export const buttonStyles = cva(
  "flex items-center justify-center rounded-lg text-sm font-medium transition outline-none focus:ring-4 disabled:pointer-events-none data-[focused=true]:ring-4 [&>svg]:text-current! data-[pending=true]:cursor-wait data-[pending=true]:opacity-60",
  {
    variants: {
      variant: {
        primary: "",
        danger: "",
        success: "",
        ghost: "",
      },
      appearance: {
        fill: "",
        outline: "",
        ghost: "",
      },
      iconOnly: {
        true: "max-sm:min-w-10",
        false: "",
      },
      fullWidthOnMobile: {
        true: "max-sm:w-full",
        false: "",
      },
      // Phones (< sm) get at least a 40px touch target; desktop sizes are unchanged.
      size: {
        xs: "max-sm:min-h-10 [&>svg]:size-4",
        sm: "max-sm:min-h-10 [&>svg]:size-5",
        md: "max-sm:min-h-10 [&>svg]:size-5",
        lg: "[&>svg]:size-5",
        xl: "[&>svg]:size-6",
        xxl: "[&>svg]:size-6",
      },
    },
    compoundVariants: [
      // Disable states for Fill
      {
        variant: ["primary", "danger", "success"],
        appearance: "fill",
        className:
          "text-white-100 disabled:bg-button-disabled-background disabled:text-button-disabled-text",
      },
      // Disable states for Outline
      {
        variant: ["primary", "danger", "success"],
        appearance: "outline",
        className:
          "border disabled:border-button-outline-disabled-border disabled:bg-button-outline-disabled-background disabled:text-button-outline-disabled-text",
      },
      // Disable states for Ghost
      {
        variant: ["primary", "danger", "success"],
        appearance: "ghost",
        className: "disabled:bg-transparent disabled:text-button-outline-disabled-text",
      },

      // Primary Fill
      {
        variant: "primary",
        appearance: "fill",
        className:
          "bg-button-primary-background text-button-primary-text hover:bg-button-primary-hover-background focus:ring-button-primary-focus-ring data-[focused=true]:ring-button-primary-focus-ring",
      },
      // Primary Outline
      {
        variant: "primary",
        appearance: "outline",
        className:
          "hover:text-button-primary-outline-hover-text border-button-primary-outline-stroke bg-button-primary-outline-background text-button-primary-outline-text hover:bg-button-primary-outline-hover-background focus:ring-button-outline-focus-ring data-[focused=true]:ring-button-outline-focus-ring",
      },
      // Primary Ghost (supporting both variant="ghost" directly or variant="primary" + appearance="ghost")
      {
        variant: "primary",
        appearance: "ghost",
        className:
          "hover:text-button-primary-outline-hover-text text-button-primary-outline-text hover:bg-button-primary-outline-hover-background focus:ring-button-outline-focus-ring data-[focused=true]:ring-button-outline-focus-ring",
      },
      {
        variant: "ghost",
        className:
          "hover:text-button-primary-outline-hover-text text-button-primary-outline-text hover:bg-button-primary-outline-hover-background focus:ring-button-outline-focus-ring data-[focused=true]:ring-button-outline-focus-ring",
      },

      // Danger Fill
      {
        variant: "danger",
        appearance: "fill",
        className:
          "bg-button-error-background text-button-error-text hover:bg-button-error-hover-background focus:ring-button-error-focus-ring data-[focused=true]:ring-button-error-focus-ring",
      },
      // Danger Outline
      {
        variant: "danger",
        appearance: "outline",
        className:
          "border-button-error-outline-stroke bg-button-error-outline-background text-button-error-outline-text hover:bg-button-error-outline-hover-background hover:text-button-error-outline-hover-text focus:ring-button-error-outline-focus-ring data-[focused=true]:ring-button-error-outline-focus-ring",
      },
      // Danger Ghost
      {
        variant: "danger",
        appearance: "ghost",
        className:
          "text-button-error-outline-text hover:bg-button-error-outline-hover-background hover:text-button-error-outline-hover-text focus:ring-button-error-outline-focus-ring data-[focused=true]:ring-button-error-outline-focus-ring",
      },

      // Success Fill
      {
        variant: "success",
        appearance: "fill",
        className:
          "bg-button-success-background text-button-success-text hover:bg-button-success-hover-background focus:ring-button-success-focus-ring data-[focused=true]:ring-button-success-focus-ring",
      },
      // Success Outline
      {
        variant: "success",
        appearance: "outline",
        className:
          "border-button-success-outline-border bg-button-success-outline-background text-button-success-outline-text hover:bg-button-success-outline-hover-background hover:text-button-success-outline-hover-text focus:ring-button-success-outline-focus-ring data-[focused=true]:ring-button-success-outline-focus-ring",
      },
      // Success Ghost
      {
        variant: "success",
        appearance: "ghost",
        className:
          "text-button-success-outline-text hover:bg-button-success-outline-hover-background hover:text-button-success-outline-hover-text focus:ring-button-success-outline-focus-ring data-[focused=true]:ring-button-success-outline-focus-ring",
      },

      // Icon Only sizes
      {
        iconOnly: true,
        size: "xs",
        className: "size-7",
      },
      {
        iconOnly: true,
        size: "sm",
        className: "size-8",
      },
      {
        iconOnly: true,
        size: "md",
        className: "size-9",
      },
      {
        iconOnly: true,
        size: "lg",
        className: "size-10",
      },
      {
        iconOnly: true,
        size: "xl",
        className: "size-11",
      },
      {
        iconOnly: true,
        size: "xxl",
        className: "size-12",
      },

      // Regular sizes with Gaps from Figma
      {
        iconOnly: false,
        size: "xs",
        className: "h-7 gap-1.5 px-2 py-1",
      },
      {
        iconOnly: false,
        size: "sm",
        className: "h-8 gap-1.5 px-3 py-1.5",
      },
      {
        iconOnly: false,
        size: "md",
        className: "h-9 gap-1.5 px-3.5 py-2",
      },
      {
        iconOnly: false,
        size: "lg",
        className: "h-10 gap-1.5 px-3.5 py-2.5",
      },
      {
        iconOnly: false,
        size: "xl",
        className: "h-11 gap-1.5 px-4 py-3",
      },
      {
        iconOnly: false,
        size: "xxl",
        className: "h-12 gap-1 px-5 py-3 text-base",
      },

      // Outline sizes (Regular) - 2px taller
      {
        iconOnly: false,
        appearance: "outline",
        size: "xs",
        className: "h-7.5",
      },
      {
        iconOnly: false,
        appearance: "outline",
        size: "sm",
        className: "h-8.5",
      },
      {
        iconOnly: false,
        appearance: "outline",
        size: "md",
        className: "h-9.5",
      },
      {
        iconOnly: false,
        appearance: "outline",
        size: "lg",
        className: "h-10.5",
      },
      {
        iconOnly: false,
        appearance: "outline",
        size: "xl",
        className: "h-11.5",
      },
      {
        iconOnly: false,
        appearance: "outline",
        size: "xxl",
        className: "h-12.5",
      },

      // Outline sizes (Icon Only) - 2px larger
      {
        iconOnly: true,
        appearance: "outline",
        size: "xs",
        className: "size-7.5",
      },
      {
        iconOnly: true,
        appearance: "outline",
        size: "sm",
        className: "size-8.5",
      },
      {
        iconOnly: true,
        appearance: "outline",
        size: "md",
        className: "size-9.5",
      },
      {
        iconOnly: true,
        appearance: "outline",
        size: "lg",
        className: "size-10.5",
      },
      {
        iconOnly: true,
        appearance: "outline",
        size: "xl",
        className: "size-11.5",
      },
      {
        iconOnly: true,
        appearance: "outline",
        size: "xxl",
        className: "size-12.5",
      },
    ],
    defaultVariants: {
      variant: "primary",
      appearance: "fill",
      iconOnly: false,
      fullWidthOnMobile: false,
      size: "md",
    },
  },
);

export type ButtonProps = Omit<RACButtonProps, "onPress"> & {
  variant?: "primary" | "danger" | "success" | "ghost";
  appearance?: "fill" | "outline" | "ghost";
  iconOnly?: boolean;
  size?: "xs" | "sm" | "md" | "lg" | "xl" | "xxl";
  /** Stretch to the full width below `sm` (e.g. a page's primary action). */
  fullWidthOnMobile?: boolean;
  focused?: boolean;
  /** Text shown next to the activity indicator while pending (defaults to the button's own label). */
  pendingLabel?: string;
  /**
   * A handler that returns a Promise (an API command, export, save, delete…) puts the button in its pending state
   * until the Promise settles. Synchronous handlers (open a drawer, toggle a menu) never do.
   */
  onPress?: (event: PressEvent) => void | Promise<unknown>;
};

/**
 * Shared button. Pending (explicit `isPending` or an async `onPress` still running) mutes the button, ignores further
 * presses (no double submission), sets `aria-busy` and shows the Cupertino-style activity indicator while keeping focus.
 */
export function Button({
  variant,
  appearance,
  iconOnly,
  size = "md",
  fullWidthOnMobile,
  focused,
  children,
  className,
  isPending,
  pendingLabel,
  onPress,
  isDisabled,
  ref,
  ...props
}: ButtonProps & { ref?: Ref<HTMLButtonElement> }) {
  const [running, setRunning] = useState(false);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  const pending = !!isPending || running;
  // react-aria's Button does not forward aria-busy (it sets aria-disabled + data-pending), so set it on the element.
  const element = useRef<HTMLButtonElement | null>(null);
  useImperativeHandle(ref, () => element.current as HTMLButtonElement);
  useEffect(() => {
    if (!element.current) return;
    if (pending) element.current.setAttribute("aria-busy", "true");
    else element.current.removeAttribute("aria-busy");
  }, [pending]);
  const handlePress = onPress
    ? (event: PressEvent) => {
        const result = onPress(event);
        if (result && typeof (result as Promise<unknown>).then === "function") {
          setRunning(true);
          (result as Promise<unknown>).then(
            () => { if (mounted.current) setRunning(false); },
            () => { if (mounted.current) setRunning(false); },
          );
        }
      }
    : undefined;
  let normalizedVariant = variant;
  let normalizedAppearance = appearance;

  if (variant === "ghost") {
    normalizedVariant = "primary";
    normalizedAppearance = "ghost";
  }

  return (
    <RACButton
      data-focused={focused ? "true" : undefined}
      isPending={pending}
      // Pending wins over a caller's `isDisabled={busy}`: react-aria still ignores presses, but the button keeps focus
      // and gets the pending (muted, busy, indicator) presentation instead of looking plainly disabled.
      isDisabled={pending ? false : isDisabled}
      onPress={handlePress}
      className={composeRenderProps(className, (className) =>
        cn(
          buttonStyles({
            variant: normalizedVariant,
            appearance: normalizedAppearance,
            iconOnly,
            size,
            fullWidthOnMobile,
          }),
          className,
        ),
      )}
      {...props}
      ref={element}
    >
      {composeRenderProps(children, (content) =>
        pending ? (
          <>
            <ActivityIndicator size={size === "xs" || size === "sm" ? "xs" : "sm"} decorative />
            {!iconOnly && (pendingLabel ? <span>{pendingLabel}</span> : content)}
          </>
        ) : (
          content
        ),
      )}
    </RACButton>
  );
}
