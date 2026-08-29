"use client";

import { ClerkProvider } from "@clerk/nextjs";
import type { ReactNode } from "react";

import { getClerkPublishableKey, isClerkConfigured } from "@/lib/auth/config";

export function ClerkAppProvider({ children }: { children: ReactNode }) {
  if (!isClerkConfigured()) {
    return children;
  }
  return <ClerkProvider publishableKey={getClerkPublishableKey()}>{children}</ClerkProvider>;
}
