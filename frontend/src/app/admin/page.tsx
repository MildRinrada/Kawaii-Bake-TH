import { redirect } from "next/navigation";

/** `/admin` is an alias for the overview. */
export default function AdminIndexPage() {
  redirect("/admin/dashboard");
}
