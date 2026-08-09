/**
 * The backend error contract, typed.
 *
 * Every non-2xx Django response has the shape
 * `{ error: { code, message, details?, request_id? } }` (single exception
 * handler, ADR 0008 family). `ApiError` carries that payload so UI code
 * can branch on `code` and map `details` onto form fields.
 */

export interface ApiErrorPayload {
  code: string;
  message: string;
  details?: Record<string, string[] | string>;
  request_id?: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, string[] | string>;
  readonly requestId?: string;

  constructor(status: number, payload?: ApiErrorPayload) {
    super(payload?.message ?? `Request failed (${status})`);
    this.name = "ApiError";
    this.status = status;
    this.code = payload?.code ?? "unknown";
    this.details = payload?.details ?? {};
    this.requestId = payload?.request_id;
  }

  /** Field-level messages for form mapping, normalised to arrays. */
  fieldErrors(): Record<string, string[]> {
    const result: Record<string, string[]> = {};
    for (const [field, value] of Object.entries(this.details)) {
      result[field] = Array.isArray(value) ? value : [value];
    }
    return result;
  }
}

/** Network-level failure (backend unreachable, CORS, timeout). */
export class NetworkError extends Error {
  constructor(cause: unknown) {
    super("ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ได้");
    this.name = "NetworkError";
    this.cause = cause;
  }
}
