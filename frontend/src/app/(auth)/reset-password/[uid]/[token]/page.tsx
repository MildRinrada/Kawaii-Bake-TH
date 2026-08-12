import { ResetPasswordScreen } from "./reset-screen";

/**
 * The landing page of the reset link in the email. The URL shape
 * (`/reset-password/{uid}/{token}`) is dictated by the backend's
 * `FRONTEND_PASSWORD_RESET_PATH` + `build_frontend_url`.
 */
export default async function ResetPasswordPage({
  params,
}: {
  params: Promise<{ uid: string; token: string }>;
}) {
  const { uid, token } = await params;
  return <ResetPasswordScreen uid={uid} token={token} />;
}
