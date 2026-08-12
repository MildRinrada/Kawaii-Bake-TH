import { Suspense } from "react";

import { AuthPanel } from "@/components/auth/auth-panel";

/**
 * `/register` and `/login` are the same panel entered from two sides;
 * the route decides which card faces the visitor first, and switching
 * afterwards slides rather than navigates (see `AuthPanel`).
 *
 * Suspense because the sign-in card behind the slider reads
 * `useSearchParams` for its `?next=` destination.
 */
export default function RegisterPage() {
  return (
    <Suspense>
      <AuthPanel initialMode="register" />
    </Suspense>
  );
}
