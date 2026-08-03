import { defineStore } from "pinia";

export interface User {
  id: string;
  email: string;
  is_active: boolean;
}

export const useAuthStore = defineStore("auth", {
  state: () => ({
    user: null as User | null,
    loading: false,
    initialized: false,
  }),
  getters: {
    isAuthenticated: (state) => !!state.user,
  },
  actions: {
    async checkAuth() {
      if (this.initialized) return;
      this.loading = true;
      try {
        const config = useRuntimeConfig();
        const apiBase = config.public.apiBase;
        // Forward cookies if checking on the server-side during SSR
        const headers = useRequestHeaders(["cookie"]) as Record<string, string>;
        const data = await $fetch<User>(`${apiBase.replace(/\/$/, "")}/api/v1/auth/me`, {
          headers,
          credentials: "include",
        });
        this.user = data;
      } catch {
        this.user = null;
      } finally {
        this.loading = false;
        this.initialized = true;
      }
    },
    async login(email: string, password: string) {
      const config = useRuntimeConfig();
      const apiBase = config.public.apiBase;
      const data = await $fetch<{ user: User }>(`${apiBase.replace(/\/$/, "")}/api/v1/auth/login`, {
        method: "POST",
        body: { email, password },
        credentials: "include",
      });
      this.user = data.user;
    },
    async logout() {
      const config = useRuntimeConfig();
      const apiBase = config.public.apiBase;
      const csrfToken = getCookie("etsy_csrf");
      const headers: Record<string, string> = {};
      if (csrfToken) {
        headers["x-csrf-token"] = csrfToken;
      }
      await $fetch(`${apiBase.replace(/\/$/, "")}/api/v1/auth/logout`, {
        method: "POST",
        headers,
        credentials: "include",
      });
      this.user = null;
      // Stale data is cleared after logging out
      this.initialized = false;
    },
  },
});

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop()?.split(";").shift() ?? null;
  return null;
}
