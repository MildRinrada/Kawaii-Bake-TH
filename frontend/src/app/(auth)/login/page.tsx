import { Suspense } from "react";

import { AuthPanel } from "@/components/auth/auth-panel";

/**
 * The sign-in side of the shared auth panel. See `/register` - one
 * surface, two entrances, and a slide between them that keeps whatever
 * was already typed.
 */
export default function LoginPage() {
  return (
    <Suspense>
      <AuthPanel initialMode="login" />
    </Suspense>
  );
}
