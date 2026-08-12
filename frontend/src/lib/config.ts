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

/**
 * Google OAuth **Web application** client id, or "" when this deployment
 * has none.
 *
 * It is a public value by design (it travels in the page anyway), and it
 * must be the same id the backend verifies against - Google signs the
 * token with the audience the button asked for, and
 * `GOOGLE_OAUTH_CLIENT_ID` on the Django side refuses anything else.
 * Empty means the sign-in button is not rendered at all: a button that
 * cannot work is worse than no button.
 */
export const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ?? "";
