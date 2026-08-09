import type { Metadata } from "next";

import { AdminShell } from "@/components/admin/admin-shell";

export const metadata: Metadata = {
  title: {
    default: "ผู้ดูแลระบบ · KawaiiBake",
    template: "%s · ผู้ดูแลระบบ",
  },
  // The admin surface is operational, never indexable.
  robots: { index: false, follow: false },
};

/**
 * Admin routes live outside the `(main)` group on purpose: they get the
 * root providers (auth, toast) but none of the learner chrome.
 */
export default function AdminLayout({ children }: LayoutProps<"/admin">) {
  return <AdminShell>{children}</AdminShell>;
}
