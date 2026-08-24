import { useAuthStore } from "~/stores/auth";

export default defineNuxtRouteMiddleware(async (to) => {
  const auth = useAuthStore();

  if (!auth.initialized) {
    await auth.checkAuth();
  }

  const isAuthPage = to.path === "/login" || to.path === "/register";
  const isProtectedPage =
    to.path === "/dashboard" ||
    to.path.startsWith("/dashboard/") ||
    to.path.startsWith("/workflow/") ||
    to.path.startsWith("/settings") ||
    to.path.startsWith("/library") ||
    to.path.startsWith("/usage");

  if (!auth.isAuthenticated && isProtectedPage) {
    return navigateTo("/login");
  }

  if (auth.isAuthenticated && isAuthPage) {
    return navigateTo("/dashboard");
  }
});
