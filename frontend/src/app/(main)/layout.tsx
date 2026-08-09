import { AppShell } from "@/components/layout/app-shell";

/** Every main-area route renders inside the shared application chrome. */
export default function MainLayout({ children }: LayoutProps<"/">) {
  return <AppShell>{children}</AppShell>;
}
