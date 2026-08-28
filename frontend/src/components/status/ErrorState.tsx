import { getErrorMessage } from "@/lib/api/errors";
import { cn } from "@/lib/cn";

interface ErrorStateProps {
  error?: unknown;
  title?: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({
  error,
  title = "Something went wrong",
  onRetry,
  className,
}: ErrorStateProps) {
  const message = getErrorMessage(error);

  return (
    <section
      role="alert"
      className={cn(
        "rounded-2xl border border-danger/30 bg-danger-light px-6 py-8 text-danger",
        className,
      )}
    >
      <h2 className="font-display text-2xl text-danger">{title}</h2>
      <p className="mt-2 text-sm sm:text-base">{message}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-5 inline-flex min-h-11 items-center rounded-xl bg-danger px-4 font-semibold text-white hover:bg-[#912018] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-danger"
        >
          Try again
        </button>
      ) : null}
    </section>
  );
}
