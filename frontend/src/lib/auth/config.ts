/** Clerk publishable configuration. Secret keys must never appear here or in NEXT_PUBLIC_*. */

export function getClerkPublishableKey(): string {
  return process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY?.trim() ?? "";
}

export function isClerkConfigured(): boolean {
  return getClerkPublishableKey().length > 0;
}
