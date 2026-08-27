import { ReactNode } from "react";

import { cn } from "@/lib/cn";

interface EmptyStateProps {
  title: string;
  description: string;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ title, description, action, className }: EmptyStateProps) {
  return (
    <section
      className={cn(
        "rounded-2xl border border-dashed border-paper-muted bg-paper-card px-6 py-10 text-center",
        className,
      )}
    >
      <h2 className="font-display text-2xl text-ink">{title}</h2>
      <p className="mx-auto mt-3 max-w-xl text-ink-muted">{description}</p>
      {action ? <div className="mt-6">{action}</div> : null}
    </section>
  );
}
