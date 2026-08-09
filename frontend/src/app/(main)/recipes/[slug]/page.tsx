import { RecipeDetailScreen } from "./recipe-detail";

export default async function RecipeDetailPage({
  params,
}: PageProps<"/recipes/[slug]">) {
  const { slug } = await params;
  return <RecipeDetailScreen slug={decodeURIComponent(slug)} />;
}
