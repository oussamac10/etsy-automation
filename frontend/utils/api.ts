/**
 * Centralized API error message extraction.
 */
export function getApiErrorMessage(err: unknown, fallback: string = "An unexpected error occurred."): string {
  if (!err) return fallback;
  if (typeof err === "string") return err;
  const errObj = err as any;
  return (
    errObj?.data?.detail ||
    errObj?.data?.message ||
    errObj?.response?._data?.detail ||
    errObj?.response?._data?.message ||
    errObj?.message ||
    fallback
  );
}

/**
 * Extract a cookie by name in browser context.
 */
export function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

/**
 * Return standard headers with CSRF token for mutating HTTP requests.
 */
export function getCsrfHeaders(): Record<string, string> {
  const csrf = getCookie("etsy_csrf");
  const headers: Record<string, string> = {
    Accept: "application/json",
  };
  if (csrf) {
    headers["x-csrf-token"] = csrf;
  }
  return headers;
}
