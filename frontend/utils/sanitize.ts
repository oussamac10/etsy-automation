/**
 * Utility functions for URL sanitization to prevent XSS attacks in dynamic attribute bindings.
 */

const ALLOWED_PROTOCOLS = ["http:", "https:", "blob:"];

/**
 * Sanitize a URL before binding to `href`, `src`, or other dynamic attributes.
 * Rejects `javascript:`, `data:text/html`, vbscript:, and malformed URIs.
 *
 * @param url - The input URL to sanitize
 * @param fallback - Fallback URL to return if invalid (defaults to '#')
 * @returns Safe URL string
 */
export function sanitizeUrl(url?: string | null, fallback = "#"): string {
  if (!url || typeof url !== "string") {
    return fallback;
  }

  const trimmed = url.trim();
  if (trimmed === "" || trimmed === "#") {
    return fallback;
  }

  // Allow relative URLs starting with / or ./ or #
  if (trimmed.startsWith("/") && !trimmed.startsWith("//")) {
    return trimmed;
  }

  try {
    const parsed = new URL(trimmed, "http://localhost");
    if (ALLOWED_PROTOCOLS.includes(parsed.protocol)) {
      return trimmed;
    }
  } catch {
    // If URL parsing fails, check if relative or return fallback
    if (trimmed.startsWith("/") || trimmed.startsWith("#")) {
      return trimmed;
    }
  }

  return fallback;
}
