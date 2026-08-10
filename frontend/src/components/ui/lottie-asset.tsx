"use client";

/**
 * A local `.lottie` animation from `public/lottie/`.
 *
 * Two ready-made shapes cover every use on the site so far:
 *
 * - `LottieLoop` — plays continuously (the assistant's bot avatar). Off
 *   entirely under `prefers-reduced-motion`, where it falls back to the
 *   animation's own first frame as a static image.
 * - `LottieHover` — idle until the pointer enters, then plays once (the
 *   notification bell). A `focus`/`blur` pair mirrors the hover so the
 *   same cue reaches keyboard users; disabled the same way under
 *   `prefers-reduced-motion`.
 *
 * `className` sizes an outer wrapper, never the `<canvas>` directly. The
 * player's `autoResize` redraws its bitmap from *container* size changes
 * — sizing the canvas element itself only stretches whatever bitmap it
 * already has, which is exactly what read as "blurry when made bigger".
 * The canvas instead fills the sized wrapper at 100%, so autoResize sees
 * a real container resize and re-rasterises at the new size times
 * `devicePixelRatio`, staying crisp at any size the wrapper is given.
 *
 * Both render nothing server-side and mount the player only in the
 * browser — `.lottie` playback is canvas-based and has no meaningful SSR
 * output.
 */

import { useRef, useSyncExternalStore } from "react";
import type { DotLottie } from "@lottiefiles/dotlottie-react";
import { DotLottieReact } from "@lottiefiles/dotlottie-react";

import { cn } from "@/lib/cn";

const QUERY = "(prefers-reduced-motion: reduce)";

function subscribeReducedMotion(onChange: () => void): () => void {
  const query = window.matchMedia(QUERY);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

function getReducedMotionSnapshot(): boolean {
  return window.matchMedia(QUERY).matches;
}

/** Subscribes to the media query directly — no effect, no render-then-fix. */
function usePrefersReducedMotion(): boolean {
  return useSyncExternalStore(
    subscribeReducedMotion,
    getReducedMotionSnapshot,
    () => false,
  );
}

/** Renders at native resolution regardless of display density. */
const RENDER_CONFIG = { autoResize: true, devicePixelRatio: 2 };

export function LottieLoop({
  src,
  className,
}: {
  src: string;
  className?: string;
}) {
  const reduced = usePrefersReducedMotion();
  return (
    <span className={cn("inline-block pointer-events-none", className)}>
      <DotLottieReact
        src={src}
        loop={!reduced}
        autoplay={!reduced}
        renderConfig={RENDER_CONFIG}
        className="size-full"
      />
    </span>
  );
}

export function LottieHover({
  src,
  className,
}: {
  src: string;
  className?: string;
}) {
  const reduced = usePrefersReducedMotion();
  const player = useRef<DotLottie | null>(null);

  function play() {
    if (reduced) return;
    player.current?.setFrame(0);
    player.current?.play();
  }

  return (
    <span className={cn("inline-block", className)}>
      <DotLottieReact
        src={src}
        autoplay={false}
        loop={false}
        renderConfig={RENDER_CONFIG}
        dotLottieRefCallback={(instance) => {
          player.current = instance;
        }}
        onMouseEnter={play}
        onFocus={play}
        className="size-full"
      />
    </span>
  );
}
