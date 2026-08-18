export default defineNuxtPlugin(() => {
  const config = useRuntimeConfig();
  if (typeof window !== "undefined" && config.public.apiBase) {
    try {
      const parsed = new URL(config.public.apiBase as string);
      if (parsed.hostname !== window.location.hostname) {
        parsed.hostname = window.location.hostname;
        config.public.apiBase = parsed.origin;
      }
    } catch {
      // keep fallback
    }
  }
});
