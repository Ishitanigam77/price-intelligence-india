import { cn } from "@/lib/cn";

interface LoadingSkeletonProps {
  label?: string;
  rows?: number;
  className?: string;
}

export function LoadingSkeleton({ label = "Loading", rows = 3, className }: LoadingSkeletonProps) {
  return (
    <div role="status" aria-live="polite" aria-busy="true" className={cn("space-y-3", className)}>
      <span className="sr-only">{label}…</span>
      {Array.from({ length: rows }, (_, index) => (
        <div
          key={index}
          className="h-24 animate-pulse rounded-2xl bg-paper-muted"
          aria-hidden="true"
        />
      ))}
    </div>
  );
}
