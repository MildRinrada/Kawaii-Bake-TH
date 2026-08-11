import { Composer } from "./composer";

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function ComposeNotificationPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  return (
    <Composer
      editId={first(params.edit)}
      fromId={first(params.from)}
      templateId={first(params.template)}
      presetKind={first(params.kind)}
    />
  );
}
