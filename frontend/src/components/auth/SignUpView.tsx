"use client";

import { SignUp } from "@clerk/nextjs";

import { isClerkConfigured } from "@/lib/auth/config";

export function SignUpView() {
  if (!isClerkConfigured()) {
    return (
      <section className="mx-auto max-w-lg space-y-4 rounded-2xl border border-paper-muted bg-paper-card p-6 shadow-card">
        <h1 className="font-display text-3xl text-ink">Create an account</h1>
        <p className="text-ink-muted">
          Clerk is not configured in this environment, so sign-up is unavailable. Application
          passwords are never stored here — identity is provided by Clerk once the publishable key
          is set.
        </p>
      </section>
    );
  }

  return (
    <div className="flex justify-center">
      <SignUp routing="path" path="/sign-up" signInUrl="/sign-in" />
    </div>
  );
}
