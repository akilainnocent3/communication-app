/**
 * Same-site redirect targets. Only a relative path that starts with a single "/" is accepted,
 * so `?next=` can never send a signed-in user to another origin (//evil, https://evil,
 * javascript:, /\evil). Auth pages are refused to avoid redirect loops.
 */
const PROBE_ORIGIN = "https://same-site.invalid";
const AUTH_PATHS = ["/login", "/connect"];

export function safeNext(value: string | null | undefined): string | null {
  if (typeof value !== "string") return null;
  const path = value.trim();
  if (!path.startsWith("/") || path.startsWith("//") || path.includes("\\") || path.length > 500) return null;
  if (/[\u0000-\u001f\u007f]/.test(path)) return null;
  let url: URL;
  try {
    url = new URL(path, PROBE_ORIGIN);
  } catch {
    return null;
  }
  if (url.origin !== PROBE_ORIGIN) return null;
  if (AUTH_PATHS.some((auth) => url.pathname === auth || url.pathname.startsWith(`${auth}/`))) return null;
  return url.pathname + url.search + url.hash;
}

/** `/login?next=<path>` for the current location (no `next` for the home route). */
export function loginHref(next: string | null | undefined) {
  const target = safeNext(next);
  return target && target !== "/" ? `/login?next=${encodeURIComponent(target)}` : "/login";
}
