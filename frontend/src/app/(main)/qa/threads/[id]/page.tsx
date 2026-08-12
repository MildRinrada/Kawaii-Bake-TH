import { redirect } from "next/navigation";

/**
 * Legacy path shim. Q&A notification snapshots delivered before the
 * board moved to `/threads` store `/qa/threads/{id}` links - delivered
 * rows are never rewritten, so this route must keep resolving.
 */
export default async function LegacyQaThreadPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  redirect(`/threads/${id}`);
}
