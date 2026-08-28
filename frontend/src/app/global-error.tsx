"use client";

import { ErrorState } from "@/components/status/ErrorState";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
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
