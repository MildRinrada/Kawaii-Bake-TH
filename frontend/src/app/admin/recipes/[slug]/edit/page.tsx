import { EditRecipeScreen } from "./edit-screen";

export default async function AdminRecipeEditPage({
  params,
}: PageProps<"/admin/recipes/[slug]/edit">) {
  const { slug } = await params;
  return <EditRecipeScreen slug={decodeURIComponent(slug)} />;
}
