import Link from "next/link";

import { EmptyState } from "@/components/status/EmptyState";

export function SignInRequired({ resource }: { resource: string }) {
  return (
    <EmptyState
      title="Sign in required"
      description={`Sign in to view your ${resource}. This page never shows another user's data.`}
      action={
        <Link
          href="/sign-in"
          className="inline-flex min-h-11 items-center rounded-xl bg-brand px-4 text-sm font-semibold text-white hover:bg-brand-dark"
        >
          Sign in
        </Link>
      }
    />
  );
}
