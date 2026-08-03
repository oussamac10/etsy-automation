import { useAuthStore } from "~/stores/auth";

export default defineNuxtRouteMiddleware(async (to) => {
  const auth = useAuthStore();

  if (!auth.initialized) {
    await auth.checkAuth();
  }

  const isAuthPage = to.path === "/login" || to.path === "/register";

  if (!auth.isAuthenticated && !isAuthPage) {
    return navigateTo("/login");
  }

  if (auth.isAuthenticated && isAuthPage) {
    return navigateTo("/");
  }
});
