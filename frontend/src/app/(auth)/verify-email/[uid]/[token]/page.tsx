import { VerifyEmailScreen } from "./verify-screen";

export default async function VerifyEmailPage({
  params,
}: {
  params: Promise<{ uid: string; token: string }>;
}) {
  const { uid, token } = await params;
  return <VerifyEmailScreen uid={uid} token={token} />;
}
