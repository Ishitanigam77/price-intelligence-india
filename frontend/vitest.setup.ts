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
