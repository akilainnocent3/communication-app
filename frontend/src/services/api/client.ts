/**
 * Same-origin API client. Next.js rewrites /api/v1/* to Django, so the session and CSRF cookies stay first-party.
 * Errors always arrive as {code, detail, errors}; `ApiError` carries them with a friendly message.
 */

export const SESSION_EXPIRED_EVENT = "cm:session-expired";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public errors: Record<string, unknown> = {}) {
    super(message);
  }
}

/** Message for an error response without a JSON body (proxy or gateway pages). */
export function statusMessage(status: number): string {
  if (status === 413) return "The file is too large for the server. The limit is 25 MB.";
  if (status === 502 || status === 503 || status === 504) return "The server is restarting or busy. Try again in a moment.";
  if (status === 401) return "Your session has ended. Sign in again.";
  if (status === 403) return "You don't have permission to do this.";
  if (status === 404) return "This item was not found. It may have been deleted.";
  if (status >= 500) return `The server hit an error (HTTP ${status}). Try again; if it keeps failing, contact your administrator.`;
  return `The request failed (HTTP ${status}). Try again.`;
}

function readCookie(name: string): string {
  if (typeof document === "undefined") return "";
  const match = document.cookie.split("; ").find((row) => row.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.split("=")[1]) : "";
}

let csrfPromise: Promise<string> | null = null;

/** The CSRF token from the cookie, fetching it once if the cookie is missing. Login rotates it, so read it each time. */
async function csrfToken(): Promise<string> {
  const cookie = readCookie("cm_csrftoken");
  if (cookie) return cookie;
  csrfPromise ??= request<{ csrf_token: string }>("auth/csrf/").then((data) => data.csrf_token).finally(() => { csrfPromise = null; });
  return csrfPromise;
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(`/api/v1/${path}`, { ...options, headers, credentials: "same-origin", cache: "no-store" });
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && typeof window !== "undefined") window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
    throw new ApiError(response.status, data?.code || "request_error", data?.detail || statusMessage(response.status), data?.errors || {});
  }
  if (data === null) throw new ApiError(response.status, "invalid_response", "The server returned an invalid response.");
  return data as T;
}

export async function mutate<T>(path: string, method: "POST" | "PUT" | "PATCH" | "DELETE", body?: unknown, signal?: AbortSignal): Promise<T> {
  const token = await csrfToken();
  return request<T>(path, {
    method,
    signal,
    headers: { "X-CSRFToken": token },
    body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body),
  });
}

/** Upload with progress (fetch has no upload progress events). */
export function upload<T>(path: string, form: FormData, onProgress?: (fraction: number) => void): Promise<T> {
  return csrfToken().then(
    (token) =>
      new Promise<T>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", `/api/v1/${path}`);
        xhr.withCredentials = true;
        xhr.setRequestHeader("X-CSRFToken", token);
        xhr.setRequestHeader("Accept", "application/json");
        xhr.upload.onprogress = (event) => event.lengthComputable && onProgress?.(event.loaded / event.total);
        xhr.onload = () => {
          let data: { code?: string; detail?: string; errors?: Record<string, unknown> } | null = null;
          try { data = JSON.parse(xhr.responseText); } catch { data = null; }
          if (xhr.status >= 200 && xhr.status < 300) resolve(data as T);
          else reject(new ApiError(xhr.status, data?.code || "upload_error", data?.detail || statusMessage(xhr.status), data?.errors || {}));
        };
        xhr.onerror = () => reject(new TypeError("Network request failed"));
        xhr.send(form);
      }),
  );
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof TypeError && /fetch|network|load failed/i.test(error.message)) return "Couldn't reach the server. Check your connection and try again.";
  return error instanceof Error ? error.message : "Something went wrong. Try again.";
}

/** First message for a form field from an ApiError's `errors`. */
export function fieldError(error: unknown, field: string): string | undefined {
  if (!(error instanceof ApiError)) return undefined;
  const value = error.errors[field];
  if (Array.isArray(value)) return String(value[0]);
  return typeof value === "string" ? value : undefined;
}

export function query(params: Record<string, string | number | boolean | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  const text = search.toString();
  return text ? `?${text}` : "";
}
