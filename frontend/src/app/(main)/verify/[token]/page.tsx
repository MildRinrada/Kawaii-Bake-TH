import { VerifyScreen } from "./verify-screen";

export default async function VerifyCertificatePage({
  params,
}: PageProps<"/verify/[token]">) {
  const { token } = await params;
  return <VerifyScreen token={decodeURIComponent(token)} />;
}
