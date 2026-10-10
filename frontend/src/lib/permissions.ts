/** True when the permission list grants any of the wanted permissions (no requirement = visible). */
export function canSee(permissions: readonly string[] | undefined, wanted?: string | readonly string[]) {
  if (!wanted || (Array.isArray(wanted) && !wanted.length)) return true;
  if (!permissions) return false;
  if (permissions.includes("*")) return true;
  const list = typeof wanted === "string" ? [wanted] : wanted;
  return list.some((code) => permissions.includes(code));
}
