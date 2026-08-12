"use client";

/**
 * "ต่อด้วย Google" - Google Identity Services, rendered by Google.
 *
 * The button is drawn by GIS itself rather than reimplemented: the
 * branding rules are theirs, and a hand-made lookalike is both a
 * guideline violation and a thing users have learnt to distrust.
 *
 * It renders **only** when this deployment has a client id
 * (`NEXT_PUBLIC_GOOGLE_CLIENT_ID`). Without one there is nothing to sign
 * in against, and a button that always fails is worse than no button -
 * so the whole block, divider included, disappears.
 *
 * What comes back from Google is an ID token; it is not read here. It
 * goes straight to `POST /auth/google/`, which verifies it against the
 * same client id server-side. Anything the browser decoded from it would
 * be unverified by definition.
 */

import { useEffect, useRef, useState } from "react";

import { ApiError } from "@/lib/api/errors";
import { GOOGLE_CLIENT_ID } from "@/lib/config";
import { useAuth } from "@/lib/auth/auth-context";

const SCRIPT_SRC = "https://accounts.google.com/gsi/client";

interface GoogleIdentityServices {
  accounts: {
    id: {
      initialize: (config: {
        client_id: string;
        callback: (response: { credential: string }) => void;
        ux_mode?: "popup" | "redirect";
      }) => void;
      renderButton: (
        parent: HTMLElement,
        options: Record<string, string | number>,
      ) => void;
    };
  };
}

declare global {
  interface Window {
    google?: GoogleIdentityServices;
  }
}

/** Load the GIS script once per document, shared by every caller. */
function loadGoogleScript(): Promise<void> {
  if (typeof document === "undefined") return Promise.resolve();
  const existing = document.querySelector<HTMLScriptElement>(
    `script[src="${SCRIPT_SRC}"]`,
  );
  if (existing?.dataset.loaded === "true") return Promise.resolve();

  return new Promise((resolve, reject) => {
    const script = existing ?? document.createElement("script");
    script.addEventListener("load", () => {
      script.dataset.loaded = "true";
      resolve();
    });
    script.addEventListener("error", () => reject(new Error("gsi")));
    if (!existing) {
      script.src = SCRIPT_SRC;
      script.async = true;
      document.head.append(script);
    }
  });
}

export function GoogleSignIn({
  onSignedIn,
  label = "สมัคร",
}: {
  /** Where to go once the session exists. */
  onSignedIn: () => void;
  /** Wording of the consent line: "สมัคร" or "เข้าสู่ระบบ". */
  label?: string;
}) {
  const { signInWithGoogle } = useAuth();
  const target = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  // The GIS callback is registered once; this keeps it pointing at the
  // current props without re-initialising (and re-drawing) the button.
  const handler = useRef<(credential: string) => void>(() => {});
  useEffect(() => {
    handler.current = (credential: string) => {
      setError(null);
      signInWithGoogle(credential).then(onSignedIn, (cause: unknown) => {
        if (
          cause instanceof ApiError &&
          cause.code === "social_email_unverified"
        ) {
          setError("บัญชี Google นี้ยังไม่ได้ยืนยันอีเมล ลองสมัครด้วยอีเมลแทนนะ");
        } else if (cause instanceof ApiError && cause.status === 503) {
          setError("ตอนนี้ยังเชื่อมต่อ Google ไม่ได้ ลองสมัครด้วยอีเมลไปก่อนนะ");
        } else {
          setError("เข้าสู่ระบบด้วย Google ไม่สำเร็จ ลองใหม่อีกครั้ง");
        }
      });
    };
  }, [signInWithGoogle, onSignedIn]);

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return;
    let cancelled = false;
    loadGoogleScript().then(
      () => {
        if (cancelled || !target.current || !window.google) return;
        window.google.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: (response) => handler.current(response.credential),
        });
        window.google.accounts.id.renderButton(target.current, {
          type: "standard",
          theme: "outline",
          size: "large",
          text: "continue_with",
          shape: "pill",
          logo_alignment: "center",
          locale: "th",
          width: 320,
        });
        setReady(true);
      },
      () => {
        if (!cancelled) setError("โหลดปุ่ม Google ไม่สำเร็จ");
      },
    );
    return () => {
      cancelled = true;
    };
  }, []);

  if (!GOOGLE_CLIENT_ID) return null;

  return (
    <div className="space-y-3">
      <div className="flex min-h-11 justify-center">
        <div ref={target} />
        {ready ? null : (
          <span
            aria-hidden
            className="h-11 w-80 max-w-full animate-pulse rounded-full bg-surface-sunken"
          />
        )}
      </div>
      {error ? (
        <p role="alert" className="text-center text-sm text-danger">
          {error}
        </p>
      ) : null}
      <p className="text-center text-xs leading-relaxed text-fg-muted">
        การ{label}ด้วย Google ถือว่าคุณยอมรับข้อตกลงการใช้งานและนโยบายความเป็นส่วนตัว
      </p>
      <div className="flex items-center gap-3">
        <span className="h-px flex-1 bg-edge" />
        <span className="text-xs text-fg-subtle">หรือ</span>
        <span className="h-px flex-1 bg-edge" />
      </div>
    </div>
  );
}
