"use client";

import { ErrorState } from "@/components/status/ErrorState";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return <ErrorState title="This page could not be displayed" error={error} onRetry={reset} />;
}
