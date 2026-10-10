"use client";

import {
  TextField,
  Label,
  FieldError,
  Text,
  type TextFieldProps,
} from "react-aria-components";
import { Input } from "@/components/tailgrids/core/input";

export function Field({
  label,
  error,
  list,
  placeholder,
  hint,
  ...props
}: TextFieldProps & { label: string; error?: string; list?: string; placeholder?: string; hint?: React.ReactNode }) {
  return (
    <TextField
      {...props}
      isInvalid={!!error || props.isInvalid}
      className="flex min-w-0 flex-col gap-2 text-sm text-text-primary"
    >
      <Label>{label}</Label>
      <Input className="w-full" list={list} placeholder={placeholder} />
      {hint && !error && <Text slot="description" className="text-xs text-text-tertiary">{hint}</Text>}
      <FieldError className="text-error-500">{error}</FieldError>
    </TextField>
  );
}
