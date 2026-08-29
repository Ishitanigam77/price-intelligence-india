import type { Metadata } from "next";

import { SignUpView } from "@/components/auth/SignUpView";

export const metadata: Metadata = {
  title: "Sign up",
};

export const dynamic = "force-dynamic";

export default function SignUpPage() {
  return <SignUpView />;
}
