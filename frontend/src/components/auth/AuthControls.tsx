"use client";

import { SignInButton, SignUpButton, SignedIn, SignedOut, UserButton } from "@clerk/nextjs";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/cn";
import { isClerkConfigured } from "@/lib/auth/config";

const ACCOUNT_NAV = [
  { href: "/watchlist", label: "Watchlist" },
  { href: "/alerts", label: "Alerts" },
  { href: "/profile", label: "Profile" },
];

const buttonClass =
  "inline-flex min-h-9 items-center rounded-lg px-3 py-1.5 text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";

export function AuthControls() {
  const pathname = usePathname();

  if (!isClerkConfigured()) {
    return (
      <Link
        href="/sign-in"
        className={cn(buttonClass, "text-ink-muted hover:bg-paper-muted hover:text-ink")}
      >
        Sign in
      </Link>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-1">
      <SignedIn>
        {ACCOUNT_NAV.map((item) => {
          const current = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={current ? "page" : undefined}
              className={cn(
                "rounded-lg px-3 py-2 text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand",
                current
                  ? "bg-brand-light text-brand-dark"
                  : "text-ink-muted hover:bg-paper-muted hover:text-ink",
              )}
            >
              {item.label}
            </Link>
          );
        })}
        <UserButton />
      </SignedIn>
      <SignedOut>
        <SignInButton mode="redirect">
          <button type="button" className={cn(buttonClass, "text-ink-muted hover:bg-paper-muted")}>
            Sign in
          </button>
        </SignInButton>
        <SignUpButton mode="redirect">
          <button
            type="button"
            className={cn(buttonClass, "bg-brand text-white hover:bg-brand-dark")}
          >
            Sign up
          </button>
        </SignUpButton>
      </SignedOut>
    </div>
  );
}
