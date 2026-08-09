import { PostDetailScreen } from "./post-detail";

export default async function CommunityPostPage({
  params,
}: PageProps<"/community/posts/[id]">) {
  const { id } = await params;
  return <PostDetailScreen id={id} />;
}
