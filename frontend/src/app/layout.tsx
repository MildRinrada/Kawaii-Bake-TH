import type { Metadata } from "next";
import { Dancing_Script, Mitr, Noto_Sans_Thai } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth/auth-context";
import { ToastProvider } from "@/components/ui/toast";
import { ClientGuard } from "@/lib/security/client-guard";

// Thai-first typography: Mitr (rounded, friendly) for display text,
// Noto Sans Thai for body  both cover Thai + Latin natively so mixed
// text never falls back mid-sentence.
const display = Mitr({
  variable: "--font-display",
  weight: ["400", "500", "600"],
  subsets: ["thai", "latin"],
});
const body = Noto_Sans_Thai({
  variable: "--font-body",
  weight: ["400", "500", "600", "700"],
  subsets: ["thai", "latin"],
});
// The certificate's signature line only  KawaiiBake's own wordmark is
// Latin, so a script face works there without needing Thai cursive
// support, which does not really exist as a legible face.
const signature = Dancing_Script({
  variable: "--font-signature",
  weight: ["500", "700"],
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "KawaiiBake",
    template: "%s · KawaiiBake",
  },
  description: "แพลตฟอร์มเรียนทำเบเกอรี่  สูตร คอร์ส แบบทดสอบ และผู้ช่วย AI",
};

/**
 * Root layout: providers only, no visual chrome.
 *
 * `lang="th"`  the platform is Thai-first. The font is the neutral
 * system stack from tokens.css; the design phase decides typography by
 * editing tokens, not this file.
 */
export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="th"
      className={`${display.variable} ${body.variable} ${signature.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col">
        <AuthProvider>
          <ToastProvider>{children}</ToastProvider>
          {/* Renders nothing; reads its posture from the backend policy
              and does nothing at all when that says `off` (ADR 0025). */}
          <ClientGuard />
        </AuthProvider>
      </body>
    </html>
  );
}
