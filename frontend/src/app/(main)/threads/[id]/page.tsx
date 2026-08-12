import { ThreadDetail } from "./thread-detail";

export default async function ThreadPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ThreadDetail threadId={id} />;
}
