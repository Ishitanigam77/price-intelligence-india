"use client";

import { useCallback, useEffect, useState } from "react";

export type AsyncState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: T }
  | { status: "error"; error: unknown };

export function useAsync<T>(
  producer: () => Promise<T>,
  deps: ReadonlyArray<unknown>,
  options?: { enabled?: boolean },
): AsyncState<T> & { reload: () => void } {
  const enabled = options?.enabled ?? true;
  const [reloadToken, setReloadToken] = useState(0);
  const requestKey = `${enabled}:${reloadToken}:${JSON.stringify(deps)}`;
  const [result, setResult] = useState<{ key: string; state: AsyncState<T> }>({
    key: "",
    state: { status: "idle" },
  });

  const reload = useCallback(() => {
    setReloadToken((token) => token + 1);
  }, []);

  useEffect(() => {
    if (!enabled) {
      return;
    }
    let cancelled = false;
    producer()
      .then((data) => {
        if (!cancelled) {
          setResult({ key: requestKey, state: { status: "success", data } });
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setResult({ key: requestKey, state: { status: "error", error } });
        }
      });
    return () => {
      cancelled = true;
    };
    // producer is recreated by callers; requestKey captures the explicit inputs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestKey, enabled]);

  const state: AsyncState<T> = !enabled
    ? { status: "idle" }
    : result.key !== requestKey
      ? { status: "loading" }
      : result.state;

  return { ...state, reload };
}
