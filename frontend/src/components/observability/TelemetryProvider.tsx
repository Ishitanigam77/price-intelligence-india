"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef, type ReactNode } from "react";

import { reportFrontendError, reportFrontendNavigation } from "@/lib/observability/client";

export function TelemetryProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const startedAt = useRef(typeof performance !== "undefined" ? performance.now() : 0);

  useEffect(() => {
    const duration = typeof performance !== "undefined" ? performance.now() - startedAt.current : 0;
    startedAt.current = typeof performance !== "undefined" ? performance.now() : 0;
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
