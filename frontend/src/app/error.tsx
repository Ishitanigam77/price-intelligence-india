"use client";

import { useEffect } from "react";

import { ErrorState } from "@/components/status/ErrorState";
import { reportFrontendError } from "@/lib/observability/client";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    reportFrontendError(error);
  }, [error]);

  return <ErrorState title="This page could not be displayed" error={error} onRetry={reset} />;
}
