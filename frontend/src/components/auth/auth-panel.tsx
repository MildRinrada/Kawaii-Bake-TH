"use client";

/**
 * Sign-in and sign-up as one surface, with the card sliding between them.
 *
 * The two screens ask for the same thing from opposite sides, so they
 * share the panel: one photographic column, one card that slides.
 * Switching does **not** navigate - both forms stay mounted, the URL is
 * corrected with `history.pushState`, and a visitor who typed their
 * address into the wrong form still has it when they arrive at the right
 * one.
 *
 * Because it is a real history entry, Back works and a deep link to
 * either route still renders that side first (server-rendered, before
 * any script runs). `popstate` puts the panel back in sync.
 *
 * The card grows and shrinks with the form it holds: sign-in is shorter
 * than sign-up, and a container that snapped between the two heights
 * would undo the slide it is meant to carry. The height is measured, not
 * guessed, so a growing password checklist or an error message moves it
 * too.
 *
 * All of that movement is decoration, so it is the first thing dropped
 * under `prefers-reduced-motion`: same layout, no travel, no fade.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { AuthAside, AuthLayout, type AuthPoint } from "@/components/auth/auth-aside";
import { LoginForm } from "@/components/auth/login-form";
import { RegisterForm } from "@/components/auth/register-form";
import { cn } from "@/lib/cn";

export type AuthMode = "login" | "register";

/** The reasons to make an account, in the order they matter. */
const BENEFITS: AuthPoint[] = [
  {
    icon: "bookmark",
    title: "บันทึกสูตรที่ถูกใจ",
    body: "เก็บไว้ในที่เดียว กลับมาทำซ้ำได้ทุกเมื่อ",
  },
  {
    icon: "graduation",
    title: "เรียนคอร์สและเก็บความคืบหน้า",
    body: "เรียนต่อจากบทที่ค้างไว้ เรียนจบรับใบประกาศนียบัตร",
  },
  {
    icon: "robot",
    title: "ถามผู้ช่วย AI ตอนติดปัญหา",
    body: "แป้งไม่ขึ้น เนื้อแน่นไป ถามได้ทันทีระหว่างทำ",
  },
];

const HEADINGS: Record<AuthMode, { title: string; lead: string }> = {
  register: { title: "สมัครสมาชิก KawaiiBake", lead: "ฟรี ใช้เวลาไม่ถึงหนึ่งนาที" },
  login: { title: "ยินดีต้อนรับกลับมา", lead: "เข้าสู่ระบบเพื่อทำขนมต่อจากที่ค้างไว้" },
};

const PATHS: Record<AuthMode, string> = {
  login: "/login",
  register: "/register",
};

/** A different photograph per side, so the slide is visibly a change of
    screen and not a re-render of the same one. */
const PHOTOS: Record<AuthMode, string> = {
  register: "macaron",
  login: "cake",
};

/**
 * One pane of the slider.
 *
 * The active pane stays in flow, so the panel is correct before any
 * script runs and the measured height never disagrees with what is on
 * screen; the inactive one is lifted out so it cannot push anything
 * around. It is also taken out of the tab order and the accessibility
 * tree: a hidden form whose fields are still focusable is a trap for
 * anyone using a keyboard.
 */
function Pane({
  active,
  from,
  innerRef,
  children,
}: {
  active: boolean;
  /** Which side this pane travels from when it comes in. */
  from: "left" | "right";
  innerRef: React.RefObject<HTMLDivElement | null>;
  children: React.ReactNode;
}) {
  return (
    <div
      ref={innerRef}
      inert={!active}
      aria-hidden={!active}
      className={cn(
        "transition-[opacity,transform] duration-300 ease-out motion-reduce:transition-none",
        active
          ? "relative translate-x-0 opacity-100"
          : cn(
              "pointer-events-none absolute inset-x-0 top-0 opacity-0 motion-reduce:translate-x-0",
              from === "left" ? "-translate-x-8" : "translate-x-8",
            ),
      )}
    >
      {children}
    </div>
  );
}

export function AuthPanel({ initialMode }: { initialMode: AuthMode }) {
  const [mode, setMode] = useState<AuthMode>(initialMode);
  const loginPane = useRef<HTMLDivElement>(null);
  const registerPane = useRef<HTMLDivElement>(null);
  // `undefined` until measured, so the server-rendered panel is simply
  // as tall as its content and nothing jumps on hydration.
  const [height, setHeight] = useState<number | undefined>(undefined);

  useEffect(() => {
    const node = (mode === "login" ? loginPane : registerPane).current;
    if (!node) return;
    const sync = () => setHeight(node.getBoundingClientRect().height);
    sync();
    // Not just on mode changes: the sign-up card grows as the password
    // checklist ticks over and when a server error appears.
    const observer = new ResizeObserver(sync);
    observer.observe(node);
    return () => observer.disconnect();
  }, [mode]);

  const switchTo = useCallback((next: AuthMode) => {
    setMode(next);
    // Not `router.push`: a route change would remount both forms and
    // there would be nothing left on screen to animate.
    window.history.pushState(null, "", PATHS[next]);
  }, []);

  useEffect(() => {
    const sync = () => {
      setMode(window.location.pathname.startsWith("/register") ? "register" : "login");
    };
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, []);

  const heading = HEADINGS[mode];

  return (
    <AuthLayout
      aside={
        <AuthAside
          title={heading.title}
          lead={heading.lead}
          points={BENEFITS}
          photo={PHOTOS[mode]}
          animateKey={mode}
        />
      }
    >
      {/* `overflow-x-clip`, not `hidden`: the pane that is travelling must
          be clipped horizontally without cutting off the card's shadow
          above and below. */}
      <div
        style={{ height }}
        className="relative overflow-x-clip transition-[height] duration-300 ease-out motion-reduce:transition-none"
      >
        <Pane active={mode === "login"} from="left" innerRef={loginPane}>
          <LoginForm onSwitchToRegister={() => switchTo("register")} />
        </Pane>
        <Pane active={mode === "register"} from="right" innerRef={registerPane}>
          <RegisterForm onSwitchToLogin={() => switchTo("login")} />
        </Pane>
      </div>
    </AuthLayout>
  );
}
