import React from "react";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import LoginPage from "@/app/login/page";
import { AuthGuard } from "@/components/auth/auth-guard";
import { Sidebar } from "@/components/layout/sidebar";
import { useAuthStore } from "@/stores/auth-store";
import { mockUser } from "./mocks/data";

const replaceMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: replaceMock,
    prefetch: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
  }),
  usePathname: () => "/documents",
  useSearchParams: () => new URLSearchParams(),
  useParams: () => ({}),
}));

describe("Phase 12.2.6 Frontend Authentication Test Suite", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    replaceMock.mockClear();
  });

  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );

  it("renders LoginPage with Continue with Google button", () => {
    useAuthStore.setState({
      user: null,
      isAuthenticated: false,
      isLoading: false,
    });

    render(<LoginPage />, { wrapper: Wrapper });

    expect(screen.getByText("Sign in to FinSight")).toBeInTheDocument();
    expect(screen.getByTestId("google-login-btn")).toBeInTheDocument();
    expect(screen.getByText("Continue with Google")).toBeInTheDocument();
  });

  it("AuthGuard displays loading state when authenticating", () => {
    useAuthStore.setState({
      user: null,
      isAuthenticated: false,
      isLoading: true,
    });

    render(
      <AuthGuard>
        <div data-testid="protected-content">Protected Information</div>
      </AuthGuard>,
      { wrapper: Wrapper }
    );

    expect(screen.getByTestId("auth-loading")).toBeInTheDocument();
    expect(screen.queryByTestId("protected-content")).not.toBeInTheDocument();
  });

  it("AuthGuard redirects unauthenticated user to /login", async () => {
    const { server } = await import("./mocks/server");
    const { http, HttpResponse } = await import("msw");
    server.use(
      http.get("*/api/v1/auth/me", () => {
        return new HttpResponse(null, { status: 401 });
      })
    );

    useAuthStore.setState({
      user: null,
      isAuthenticated: false,
      isLoading: false,
    });

    render(
      <AuthGuard>
        <div data-testid="protected-content">Protected Information</div>
      </AuthGuard>,
      { wrapper: Wrapper }
    );

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith(expect.stringContaining("/login"));
    });
    expect(screen.queryByTestId("protected-content")).not.toBeInTheDocument();
  });

  it("AuthGuard renders protected content when authenticated", () => {
    useAuthStore.setState({
      user: mockUser,
      isAuthenticated: true,
      isLoading: false,
    });

    render(
      <AuthGuard>
        <div data-testid="protected-content">Protected Information</div>
      </AuthGuard>,
      { wrapper: Wrapper }
    );

    expect(screen.getByTestId("protected-content")).toBeInTheDocument();
  });

  it("Sidebar displays user profile and sign out button when authenticated", () => {
    useAuthStore.setState({
      user: mockUser,
      isAuthenticated: true,
      isLoading: false,
    });

    render(<Sidebar />, { wrapper: Wrapper });

    expect(screen.getByText(mockUser.name)).toBeInTheDocument();
    expect(screen.getByText(mockUser.email)).toBeInTheDocument();
    expect(screen.getByTestId("sidebar-signout-btn")).toBeInTheDocument();
  });

  it("Sidebar displays sign in link when unauthenticated", () => {
    useAuthStore.setState({
      user: null,
      isAuthenticated: false,
      isLoading: false,
    });

    render(<Sidebar />, { wrapper: Wrapper });

    expect(screen.getByTestId("sidebar-signin-link")).toBeInTheDocument();
    expect(screen.getByText("Sign In with Google")).toBeInTheDocument();
  });
});
