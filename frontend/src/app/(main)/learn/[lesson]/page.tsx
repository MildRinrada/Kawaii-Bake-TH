import { LessonScreen } from "./lesson-screen";

export default async function LessonPage({
  params,
}: PageProps<"/learn/[lesson]">) {
  const { lesson } = await params;
  return <LessonScreen lessonId={lesson} />;
}
