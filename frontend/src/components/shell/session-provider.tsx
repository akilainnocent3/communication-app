"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, type ReactNode } from "react";
import { ApiError, SESSION_EXPIRED_EVENT, mutate, request } from "@/services/api/client";
import type { Me, Preferences } from "@/services/api/types";
import { setTimezone } from "@/lib/format";
import { canSee } from "@/lib/permissions";

export const ME_KEY = ["auth", "me"] as const;

type Session = {
  me: Me | undefined;
  isLoading: boolean;
  /** Permission check with the same rules as the sidebar (any of `wanted`). */
  can: (wanted?: string | readonly string[]) => boolean;
  isSuperAdmin: boolean;
  preferences: Preferences;
  updatePreferences: (patch: Partial<Preferences> & { timezone?: string }) => Promise<void>;
  signOut: () => Promise<void>;
  refresh: () => Promise<unknown>;
};

const DEFAULT_PREFERENCES: Preferences = {
  shortcuts: true, density: "comfortable", reading_pane: "right", swipe_right: "archive", swipe_left: "trash", undo_send_seconds: 10,
};

const SessionContext = createContext<Session | null>(null);

export function fetchMe() {
  return request<Me>("auth/me/");
}

/** Signed-in user, role, permissions and per-platform data. Redirects to /login when there is no session. */
export function SessionProvider({ children }: { children: ReactNode }) {
  const client = useQueryClient();
  const router = useRouter();
  const pathname = usePathname();
  const query = useQuery({ queryKey: ME_KEY, queryFn: fetchMe, staleTime: 60_000, retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2 });

  const unauthenticated = query.error instanceof ApiError && (query.error.status === 401 || query.error.status === 403);
  useEffect(() => {
    if (unauthenticated) router.replace(`/login?next=${encodeURIComponent(pathname || "/")}`);
  }, [unauthenticated, router, pathname]);

  useEffect(() => {
    const onExpired = () => {
      client.clear();
      router.replace(`/login?expired=1&next=${encodeURIComponent(window.location.pathname + window.location.search)}`);
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired);
  }, [client, router]);

  const me = query.data;
  if (me) setTimezone(me.user.timezone);

  const preferences = useMemo(() => ({ ...DEFAULT_PREFERENCES, ...(me?.user.preferences as Partial<Preferences> | undefined) }), [me]);

  const updatePreferences = useCallback(async (patch: Partial<Preferences> & { timezone?: string }) => {
    const previous = client.getQueryData<Me>(ME_KEY);
    if (previous) {
      const { timezone, ...prefs } = patch;
      client.setQueryData<Me>(ME_KEY, { ...previous, user: { ...previous.user, timezone: timezone ?? previous.user.timezone, preferences: { ...previous.user.preferences, ...prefs } } });
    }
    try {
      await mutate("auth/preferences/", "PATCH", patch);
    } catch (error) {
      if (previous) client.setQueryData(ME_KEY, previous);
      throw error;
    }
  }, [client]);

  const signOut = useCallback(async () => {
    await mutate("auth/logout/", "POST");
    client.clear();
  }, [client]);

  const value = useMemo<Session>(() => ({
    me,
    isLoading: query.isPending,
    can: (wanted) => canSee(me?.permissions, wanted),
    isSuperAdmin: me?.role?.slug === "super_admin",
    preferences,
    updatePreferences,
    signOut,
    refresh: () => client.invalidateQueries({ queryKey: ME_KEY }),
  }), [me, query.isPending, preferences, updatePreferences, signOut, client]);

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside SessionProvider");
  return value;
}
