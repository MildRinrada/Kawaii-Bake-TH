import { CourseDetailScreen } from "./course-detail";

export default async function CourseDetailPage({
  params,
}: PageProps<"/courses/[slug]">) {
  const { slug } = await params;
  return <CourseDetailScreen slug={decodeURIComponent(slug)} />;
}
