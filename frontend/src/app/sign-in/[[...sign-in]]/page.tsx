import type { Metadata } from "next";

import { SignInView } from "@/components/auth/SignInView";

export const metadata: Metadata = {
  title: "Sign in",
};

export const dynamic = "force-dynamic";

export default function SignInPage() {
  return <SignInView />;
}
