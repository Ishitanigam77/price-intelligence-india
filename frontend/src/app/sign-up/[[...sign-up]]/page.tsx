import type { Metadata } from "next";

import { SignUpView } from "@/components/auth/SignUpView";

export const metadata: Metadata = {
  title: "Sign up",
};

export default function SignUpPage() {
  return <SignUpView />;
}
