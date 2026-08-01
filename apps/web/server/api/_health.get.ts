/**
 * Liveness endpoint for the Nuxt container itself.
 *
 * It deliberately does not call the API: a healthy web container with an
 * unreachable API is a different failure, and Compose should report it that way.
 */
export default defineEventHandler(() => ({
  status: "ok",
  service: "web",
  version: "0.1.0",
}));
