import { sanitizeUserErrorMessage } from "./formatters";

/**
 * Centralized API error message extraction and user-facing sanitization.
 */
export function getApiErrorMessage(err: unknown, fallback: string = "An unexpected error occurred. Please try again."): string {
  if (!err) return fallback;
  if (typeof err === "string") return sanitizeUserErrorMessage(err, fallback);
  const errObj = err as {
    data?: { detail?: string; message?: string };
    response?: { _data?: { detail?: string; message?: string } };
    message?: string;
  };
  const raw = (
    errObj?.data?.detail ||
    errObj?.data?.message ||
    errObj?.response?._data?.detail ||
    errObj?.response?._data?.message ||
    errObj?.message ||
    fallback
  );
  return sanitizeUserErrorMessage(raw, fallback);
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
