"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef, type ReactNode } from "react";

import { reportFrontendError, reportFrontendNavigation } from "@/lib/observability/client";

export function TelemetryProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const startedAt = useRef(0);

  useEffect(() => {
    const now = performance.now();
    const duration = startedAt.current === 0 ? 0 : now - startedAt.current;
    startedAt.current = now;
    reportFrontendNavigation(pathname || "/", duration);

    const onError = (event: ErrorEvent) => {
      reportFrontendError(event.error ?? event.message, pathname || "/");
    };
    const onUnhandled = (event: PromiseRejectionEvent) => {
      reportFrontendError(event.reason, pathname || "/");
    };
    window.addEventListener("error", onError);
    window.addEventListener("unhandledrejection", onUnhandled);
    return () => {
      window.removeEventListener("error", onError);
      window.removeEventListener("unhandledrejection", onUnhandled);
    };
  }, [pathname]);

  return children;
}
