"use client";

/**
 * Session-based auth state for the whole app.
 *
 * The Django session cookie is the single source of truth (ADR 0007) 
 * this context only mirrors it: on mount it asks `/users/profile/` who
 * the caller is (401/403 = anonymous), and login/register/logout call
 * the existing auth endpoints then refresh that mirror. No tokens are
 * stored anywhere in the frontend.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { OwnProfile } from "@/lib/api/models";

export type AuthStatus = "loading" | "authenticated" | "anonymous";

interface AuthContextValue {
  status: AuthStatus;
  user: OwnProfile | null;
  login: (email: string, password: string, remember?: boolean) => Promise<void>;
  register: (input: {
    email: string;
    username: string;
    password: string;
    accept_terms: boolean;
  }) => Promise<void>;
  /** Exchange a Google ID token for a session. */
  signInWithGoogle: (credential: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<OwnProfile | null>(null);

  const refresh = useCallback(async () => {
    try {
      const profile = await api.get<OwnProfile>("/users/profile/");
      setUser(profile);
      setStatus("authenticated");
    } catch (error) {
      if (error instanceof ApiError && [401, 403].includes(error.status)) {
        setUser(null);
        setStatus("anonymous");
        return;
      }
      // Backend unreachable: treat as anonymous but do not cache a user.
      setUser(null);
      setStatus("anonymous");
    }
  }, []);

  useEffect(() => {
    // Inline continuation rather than calling `refresh()` synchronously:
    // every setState here runs after an await, never during the effect.
    let cancelled = false;
    api
      .get<OwnProfile>("/users/profile/")
      .then((profile) => {
        if (cancelled) return;
        setUser(profile);
        setStatus("authenticated");
      })
      .catch(() => {
        if (cancelled) return;
        setUser(null);
        setStatus("anonymous");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(
    async (email: string, password: string, remember = false) => {
      // `remember_me` decides session lifetime server-side: 30 days, or
      // a cookie that dies with the browser.
      await api.post("/auth/login/", {
        body: { email, password, remember_me: remember },
      });
      await refresh();
    },
    [refresh],
  );

  const register = useCallback(
    async (input: {
      email: string;
      username: string;
      password: string;
      accept_terms: boolean;
    }) => {
      // The API contract wants the password twice; the form asks once and a
      // show/hide toggle replaces the confirm field.
      await api.post("/auth/register/", {
        body: { ...input, password_confirm: input.password },
      });
      // Deliberately no sign-in here: the account must confirm its email
      // first, and signing in belongs to the user after that - the
      // register page routes to the check-your-inbox screen instead.
    },
    [],
  );

  const signInWithGoogle = useCallback(
    async (credential: string) => {
      // Unlike password registration this *does* end in a session: Google
      // already proved the address, so there is no inbox step to wait for.
      // One endpoint covers both sign-up and sign-in - the visitor pressed
      // one button and should not have to know which one they did.
      await api.post("/auth/google/", { body: { credential } });
      await refresh();
    },
    [refresh],
  );

  const logout = useCallback(async () => {
    await api.post("/auth/logout/");
    setUser(null);
    setStatus("anonymous");
  }, []);

  const value = useMemo(
    () => ({
      status,
      user,
      login,
      register,
      signInWithGoogle,
      logout,
      refresh,
    }),
    [status, user, login, register, signInWithGoogle, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}
