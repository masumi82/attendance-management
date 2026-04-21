import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

export type Role = "admin" | "approver" | "member";

export type AuthUser = {
  id: string;
  email: string;
  name: string;
  role: Role;
  active: boolean;
};

type AuthState = {
  user: AuthUser | null;
  accessToken: string | null;
  refreshToken: string | null;
  isBootstrapping: boolean;
  setTokens: (access: string | null, refresh: string | null) => void;
  setUser: (user: AuthUser | null) => void;
  setBootstrapping: (v: boolean) => void;
  clear: () => void;
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isBootstrapping: true,

      setTokens: (access, refresh) =>
        set({ accessToken: access, refreshToken: refresh }),
      setUser: (user) => set({ user }),
      setBootstrapping: (v) => set({ isBootstrapping: v }),
      clear: () =>
        set({ user: null, accessToken: null, refreshToken: null }),
    }),
    {
      name: "attendance-auth",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        refreshToken: state.refreshToken,
      }),
    },
  ),
);

export const authSelectors = {
  isAuthenticated: (s: AuthState) => Boolean(s.user && s.accessToken),
  role: (s: AuthState) => s.user?.role ?? null,
};
