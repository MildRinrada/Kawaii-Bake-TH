"use client";

/**
 * Client-side route guard.
 *
 * The session cookie is httpOnly on the API origin, so the Next server
 * cannot inspect it  protection is a client concern: while auth state
 * loads we show a skeleton, and an anonymous visitor is redirected to
 * login with a `next` parameter for the round trip back.
 */

import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { useAuth } from "@/lib/auth/auth-context";
import { Skeleton } from "@/components/ui/skeleton";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === "anonymous") {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [status, router, pathname]);

  if (status !== "authenticated") {
    return (
      <div aria-busy="true" className="space-y-3 py-8">
        <Skeleton className="h-8 w-1/3" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }
  return <>{children}</>;
}
