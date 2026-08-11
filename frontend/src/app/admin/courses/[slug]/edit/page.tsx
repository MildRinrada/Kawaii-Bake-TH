import { EditCourseScreen } from "./edit-screen";

export default async function AdminCourseEditPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return <EditCourseScreen slug={slug} />;
}
