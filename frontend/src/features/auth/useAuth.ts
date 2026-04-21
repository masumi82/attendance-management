import { useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";

import {
  apiLogin,
  apiLogout,
  apiMe,
  apiRefresh,
} from "@/lib/api";
import { useAuthStore } from "@/lib/auth-store";

export function useAuth() {
  const state = useAuthStore();
  const queryClient = useQueryClient();

  // All callbacks use useAuthStore.getState() directly so that their
  // identity stays stable across renders. Depending on `state` caused
  // every store change to recreate these handlers and re-fire the
  // bootstrap effect in Root (main.tsx).
  const login = useCallback(async (email: string, password: string) => {
    const { setTokens, setUser } = useAuthStore.getState();
    const tokens = await apiLogin(email, password);
    setTokens(tokens.access_token, tokens.refresh_token);
    const user = await apiMe();
    setUser(user);
  }, []);

  const logout = useCallback(async () => {
    const { refreshToken, clear } = useAuthStore.getState();
    if (refreshToken) {
      try { await apiLogout(refreshToken); } catch { /* ignore */ }
    }
    clear();
    // Prevent cached data (admin lists, etc.) from leaking to the next
    // user that signs in on this browser.
    queryClient.clear();
  }, [queryClient]);

  const bootstrap = useCallback(async () => {
    const { refreshToken, setTokens, setUser, setBootstrapping, clear } =
      useAuthStore.getState();
    if (!refreshToken) {
      setBootstrapping(false);
      return;
    }
    try {
      const pair = await apiRefresh(refreshToken);
      setTokens(pair.access_token, pair.refresh_token);
      const user = await apiMe();
      setUser(user);
    } catch {
      clear();
    } finally {
      setBootstrapping(false);
    }
  }, []);

  return { ...state, login, logout, bootstrap };
}
