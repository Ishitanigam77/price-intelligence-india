import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

import { navigationState } from "@/test/navigation";

process.env.NEXT_PUBLIC_API_BASE_URL = "http://localhost:8000";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: (...args: unknown[]) => navigationState.push(...args),
    replace: vi.fn(),
    back: vi.fn(),
    prefetch: vi.fn(),
  }),
  usePathname: () => navigationState.pathname,
  useSearchParams: () => new URLSearchParams(navigationState.search),
}));

vi.mock("@clerk/nextjs", () => ({
  ClerkProvider: ({ children }: { children: unknown }) => children,
  SignedIn: () => null,
  SignedOut: ({ children }: { children: unknown }) => children,
  SignInButton: ({ children }: { children: unknown }) => children,
  SignUpButton: ({ children }: { children: unknown }) => children,
  SignIn: () => null,
  SignUp: () => null,
  UserButton: () => null,
  useAuth: () => ({
    isLoaded: true,
    isSignedIn: false,
    userId: null,
    getToken: async () => null,
    signOut: async () => undefined,
  }),
  useUser: () => ({
    isLoaded: true,
    isSignedIn: false,
    user: null,
  }),
}));

vi.mock("@clerk/nextjs/server", () => ({
  auth: async () => ({ userId: null }),
  currentUser: async () => null,
  clerkMiddleware: () => () => undefined,
  createRouteMatcher: () => () => false,
}));
