import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, vi } from "vitest";
import { server } from "./mocks/server";

// Mock next/navigation globally for Next.js 14 App Router hooks in JSDOM tests
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
  }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
  useParams: () => ({}),
}));

// Ensure globalThis.AbortSignal and AbortController match Node runtime globals in jsdom
if (typeof globalThis.AbortSignal !== "undefined" && typeof globalThis.AbortController !== "undefined") {
  // Polyfill symbol or prototype if necessary
}

// Start MSW Server before all test suites
beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});

// Reset handlers and cleanup DOM after each test
afterEach(() => {
  cleanup();
  server.resetHandlers();
});

// Clean up MSW Server after all tests
afterAll(() => {
  server.close();
});
