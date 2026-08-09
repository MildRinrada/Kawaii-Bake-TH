/**
 * The one HTTP client for the Django API.
 *
 * Session-cookie authentication (ADR 0007): every request carries
 * credentials, and mutating requests carry the CSRF token Django set as
 * a readable cookie. The client owns exactly three concerns — base URL,
 * credentials/CSRF, and the error contract — and no business logic.
 */

import { API_BASE_URL } from "@/lib/config";
import { ApiError, type ApiErrorPayload, NetworkError } from "@/lib/api/errors";

function readCookie(name: string): string {
  if (typeof document === "undefined") return "";
  const match = document.cookie
    .split("; ")
    .find((part) => part.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : "";
}

let csrfBootstrapped = false;

/** Ensure the CSRF cookie exists before the first mutating request. */
async function ensureCsrfCookie(): Promise<void> {
  if (csrfBootstrapped || readCookie("csrftoken")) {
    csrfBootstrapped = true;
    return;
  }
  await fetch(`${API_BASE_URL}/auth/csrf/`, { credentials: "include" });
  csrfBootstrapped = true;
}

export interface RequestOptions {
  /** Query parameters; null/undefined entries are dropped. */
  query?: Record<string, string | number | boolean | null | undefined>;
  /** JSON body for mutating requests. */
  body?: unknown;
  /** Multipart body — wins over `body` when provided. */
  formData?: FormData;
  signal?: AbortSignal;
}

const MUTATING = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export async function apiFetch<T>(
  method: string,
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const url = new URL(`${API_BASE_URL}${path}`);
  for (const [key, value] of Object.entries(options.query ?? {})) {
    if (value !== null && value !== undefined) {
      url.searchParams.set(key, String(value));
    }
  }

  const headers: Record<string, string> = { Accept: "application/json" };
  let body: BodyInit | undefined;
  if (options.formData) {
    body = options.formData;
  } else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  if (MUTATING.has(method)) {
    await ensureCsrfCookie();
    headers["X-CSRFToken"] = readCookie("csrftoken");
  }

  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers,
      body,
      credentials: "include",
      signal: options.signal,
    });
  } catch (cause) {
    throw new NetworkError(cause);
  }

  if (response.status === 204) return undefined as T;

  let payload: unknown = undefined;
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = undefined;
    }
  }

  if (!response.ok) {
    const errorPayload = (payload as { error?: ApiErrorPayload })?.error;
    throw new ApiError(response.status, errorPayload);
  }
  return payload as T;
}

export const api = {
  get: <T>(path: string, options?: RequestOptions) =>
    apiFetch<T>("GET", path, options),
  post: <T>(path: string, options?: RequestOptions) =>
    apiFetch<T>("POST", path, options),
  patch: <T>(path: string, options?: RequestOptions) =>
    apiFetch<T>("PATCH", path, options),
  put: <T>(path: string, options?: RequestOptions) =>
    apiFetch<T>("PUT", path, options),
  delete: <T>(path: string, options?: RequestOptions) =>
    apiFetch<T>("DELETE", path, options),
};

/** The standard paginated envelope every list endpoint returns. */
export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
