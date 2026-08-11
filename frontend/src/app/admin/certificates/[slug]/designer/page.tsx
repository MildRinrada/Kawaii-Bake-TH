import { CertificateDesigner } from "./designer";

export default async function CertificateDesignerPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return <CertificateDesigner slug={slug} />;
}
