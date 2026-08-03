import { useAuthStore } from "~/stores/auth";

export default defineNuxtRouteMiddleware(async (to) => {
  const auth = useAuthStore();

  if (!auth.initialized) {
    await auth.checkAuth();
  }

  if (!auth.isAuthenticated && to.path !== "/login") {
    return navigateTo("/login");
  }

  if (auth.isAuthenticated && to.path === "/login") {
    return navigateTo("/");
  }
});
