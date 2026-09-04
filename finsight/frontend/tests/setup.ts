import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "./mocks/server";

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
