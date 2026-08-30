"use client";

import { useEffect } from "react";

import { ErrorState } from "@/components/status/ErrorState";
import { reportFrontendError } from "@/lib/observability/client";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    reportFrontendError(error);
  }, [error]);
  return (
    <html lang="en-IN">
      <body>
        <main className="mx-auto max-w-page px-4 py-16">
          <ErrorState
            title="The application hit an unexpected error"
            error={error}
            onRetry={reset}
          />
        </main>
      </body>
    </html>
  );
}
