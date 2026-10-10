/** localStorage that never throws (private windows, blocked storage, SSR). Per-viewer conveniences only. */
export function readStored<T>(key: string, fallback: T): T {
  try {
    if (typeof window === "undefined") return fallback;
    const raw = window.localStorage.getItem(key);
    return raw === null ? fallback : (JSON.parse(raw) as T);
  } catch {
    return fallback;
  }
}

export function writeStored(key: string, value: unknown): void {
  try {
    if (typeof window !== "undefined") window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage unavailable: the convenience is simply not remembered */
  }
}
