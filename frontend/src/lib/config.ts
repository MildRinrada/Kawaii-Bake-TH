/**
 * Frontend environment configuration.
 *
 * Everything the browser bundle needs is `NEXT_PUBLIC_*`; see
 * `.env.example`. The API base URL points at the Django `/api/v1` root 
 * the frontend never talks to anything else.
 */
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

/** Absolute origin of the Django backend (for media URLs, if relative). */
export const API_ORIGIN = new URL(API_BASE_URL).origin;
