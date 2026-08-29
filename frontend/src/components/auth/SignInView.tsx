"use client";

import { SignIn } from "@clerk/nextjs";

import { isClerkConfigured } from "@/lib/auth/config";

export function SignInView() {
  if (!isClerkConfigured()) {
    return (
      <section className="mx-auto max-w-lg space-y-4 rounded-2xl border border-paper-muted bg-paper-card p-6 shadow-card">
        <h1 className="font-display text-3xl text-ink">Sign in</h1>
        <p className="text-ink-muted">
          Clerk is not configured in this environment. Set{" "}
          <code className="rounded bg-paper-muted px-1 py-0.5 text-sm">
            NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
          </code>{" "}
          (frontend) and{" "}
          <code className="rounded bg-paper-muted px-1 py-0.5 text-sm">CLERK_SECRET_KEY</code>{" "}
          (server-only) from placeholders in <code className="text-sm">frontend/.env.example</code>.
          This screen does not sign anyone in.
        </p>
      </section>
    );
  }

  return (
    <div className="flex justify-center">
      <SignIn routing="path" path="/sign-in" signUpUrl="/sign-up" />
    </div>
  );
}
