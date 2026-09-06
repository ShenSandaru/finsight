"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Files,
  MessageSquareText,
  FileBarChart2,
  GitCompare,
  Layers,
  ChevronLeft,
  ChevronRight,
  PanelLeft,
  LogIn,
  LogOut,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useUiStore } from "@/stores/ui-store";
import { useAuthStore } from "@/stores/auth-store";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { FinSightLogo } from "@/components/layout/finsight-logo";

interface NavItem {
  title: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
  activePattern: (pathname: string) => boolean;
}

const navItems: NavItem[] = [
  {
    title: "Dashboard",
    href: "/",
    icon: LayoutDashboard,
    activePattern: (p) => p === "/",
  },
  {
    title: "Documents",
    href: "/documents",
    icon: Files,
    activePattern: (p) => Boolean(p?.startsWith("/documents")),
  },
  {
    title: "Research",
    href: "/research",
    icon: MessageSquareText,
    activePattern: (p) => Boolean(p?.startsWith("/research")),
  },
  {
    title: "Reports",
    href: "/reports",
    icon: FileBarChart2,
    activePattern: (p) => Boolean(p?.startsWith("/reports")),
  },
  {
    title: "Compare",
    href: "/compare",
    icon: GitCompare,
    activePattern: (p) => Boolean(p?.startsWith("/compare")),
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const sidebarOpen = useUiStore((state) => state.sidebarOpen);
  const toggleSidebar = useUiStore((state) => state.toggleSidebar);
  const selectedDocumentIds = useUiStore((state) => state.selectedDocumentIds);
  const { user, isAuthenticated, logout } = useAuthStore();

  return (
    <aside
      className={`fixed inset-y-0 left-0 z-40 flex flex-col border-r bg-card transition-all duration-200 overflow-x-hidden ${
        sidebarOpen ? "w-64" : "w-16"
      }`}
      data-testid="app-sidebar"
      aria-label="Application navigation"
    >
      {/* Brand Header / ChatGPT-style Toggle */}
      {sidebarOpen ? (
        <div className="flex h-14 items-center justify-between border-b px-3">
          <Link
            href="/"
            className="flex items-center gap-2.5 overflow-hidden transition-opacity hover:opacity-85"
            aria-label="FinSight home"
          >
            <FinSightLogo size={32} className="shadow-sm" />
            <div className="flex flex-col min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="font-semibold tracking-tight text-sm text-foreground leading-none">
                  FinSight
                </span>
                <span className="rounded bg-finance-positive/10 dark:bg-finance-positive/20 text-finance-positive dark:text-finance-positive-foreground border border-finance-positive/25 px-1 py-0.2 text-[9px] font-mono font-medium leading-none uppercase tracking-wider">
                  Beta
                </span>
              </div>
              <span className="text-[10px] text-muted-foreground font-mono mt-0.5 tracking-wider">
                INVESTMENT COPILOT
              </span>
            </div>
          </Link>
          <TooltipProvider delayDuration={150}>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-muted-foreground hover:text-foreground hidden sm:inline-flex shrink-0"
                  onClick={toggleSidebar}
                  aria-label="Collapse sidebar"
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">Close sidebar</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      ) : (
        <div className="flex h-14 items-center justify-center border-b">
          <TooltipProvider delayDuration={150}>
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  onClick={toggleSidebar}
                  className="group relative flex h-9 w-9 items-center justify-center rounded-lg hover:bg-muted transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  aria-label="Expand sidebar"
                >
                  {/* Default State: Designed Logo */}
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center transition-opacity duration-150 group-hover:opacity-0">
                    <FinSightLogo size={30} className="shadow-sm" />
                  </div>
                  {/* Hover State: Sidebar Expand Icon */}
                  <div className="absolute inset-0 flex items-center justify-center text-foreground opacity-0 transition-opacity duration-150 group-hover:opacity-100">
                    <PanelLeft className="h-5 w-5" />
                  </div>
                </button>
              </TooltipTrigger>
              <TooltipContent side="right" sideOffset={10} className="font-medium text-xs">
                Open sidebar
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      )}

      {/* Nav List */}
      <nav className="flex-1 space-y-1 p-2 overflow-y-auto overflow-x-hidden">
        {navItems.map((item) => {
          const isActive = item.activePattern(pathname);
          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center rounded-md text-xs font-medium transition-colors ${
                sidebarOpen ? "gap-3 px-3 py-2" : "justify-center p-2"
              } ${
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
              title={item.title}
              data-testid={`nav-item-${item.title.toLowerCase()}`}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {sidebarOpen && (
                <div className="flex flex-1 items-center justify-between min-w-0">
                  <span className="truncate">{item.title}</span>
                  {item.badge && (
                    <span
                      className={`text-[9px] px-1.5 py-0.2 rounded font-mono tracking-wider uppercase ${
                        isActive
                          ? "bg-primary-foreground/20 text-primary-foreground"
                          : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {item.badge}
                    </span>
                  )}
                </div>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Scoped Research Documents Status, User Session & Theme Toggle in Sidebar Footer */}
      {sidebarOpen ? (
        <div className="border-t p-3 bg-muted/20 space-y-3">
          <ThemeToggle collapsed={false} />

          {/* User Account / Authentication Status */}
          <div className="border-t border-border/50 pt-2" data-testid="sidebar-user-section">
            {isAuthenticated && user ? (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/20 text-xs font-bold text-primary shrink-0">
                    {user.name ? user.name[0].toUpperCase() : "U"}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-semibold text-foreground">{user.name}</p>
                    <p className="truncate text-[10px] text-muted-foreground">{user.email}</p>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => logout()}
                  className="w-full justify-start text-xs h-7 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                  data-testid="sidebar-signout-btn"
                >
                  <LogOut className="mr-2 h-3.5 w-3.5" />
                  Sign Out
                </Button>
              </div>
            ) : (
              <Link
                href="/login"
                className="flex items-center gap-2 text-xs font-medium text-primary hover:underline"
                data-testid="sidebar-signin-link"
              >
                <LogIn className="h-4 w-4" />
                <span>Sign In with Google</span>
              </Link>
            )}
          </div>

          <div>
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="text-muted-foreground flex items-center gap-1.5">
                <Layers className="h-3.5 w-3.5 text-primary" />
                Active Context
              </span>
              <Badge
                variant={selectedDocumentIds.length > 0 ? "financePositive" : "secondary"}
                className="text-[10px] px-1.5 py-0 h-4 font-tabular-nums"
                data-testid="sidebar-selected-count"
              >
                {selectedDocumentIds.length} {selectedDocumentIds.length === 1 ? "doc" : "docs"}
              </Badge>
            </div>
            <p className="text-[11px] text-muted-foreground leading-snug">
              {selectedDocumentIds.length > 0
                ? `${selectedDocumentIds.length} filing${selectedDocumentIds.length > 1 ? "s" : ""} scoped for research queries`
                : "No filings selected. Select in Documents."}
            </p>
          </div>
        </div>
      ) : (
        <div className="border-t p-2 flex flex-col items-center gap-1 bg-muted/10">
          <ThemeToggle collapsed={true} />
          {isAuthenticated && user ? (
            <button
              onClick={() => logout()}
              title={`Signed in as ${user.name} (${user.email}). Click to Sign Out.`}
              className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/20 text-xs font-bold text-primary hover:bg-destructive/20 hover:text-destructive transition-colors mt-1"
              data-testid="sidebar-collapsed-user-avatar"
            >
              {user.name ? user.name[0].toUpperCase() : "U"}
            </button>
          ) : (
            <Link
              href="/login"
              title="Sign In"
              className="p-1.5 rounded hover:bg-muted/50 transition-colors mt-1"
              data-testid="sidebar-collapsed-signin-btn"
            >
              <LogIn className="h-4 w-4 text-primary shrink-0" />
            </Link>
          )}
          <Link
            href="/documents"
            className="flex flex-col items-center justify-center p-1.5 rounded hover:bg-muted/50 transition-colors w-full"
            title={`${selectedDocumentIds.length} filings in active context`}
            aria-label={`${selectedDocumentIds.length} filings in active context`}
            data-testid="sidebar-collapsed-context-badge"
          >
            <Layers className="h-4 w-4 text-primary shrink-0" />
            <span className="text-[10px] font-mono font-bold text-foreground mt-0.5 font-tabular-nums">
              {selectedDocumentIds.length}
            </span>
          </Link>
        </div>
      )}
    </aside>
  );
}
