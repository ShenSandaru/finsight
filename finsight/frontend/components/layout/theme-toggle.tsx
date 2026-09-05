"use client";

import React, { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Sun, Moon, Monitor } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface ThemeToggleProps {
  collapsed?: boolean;
}

export function ThemeToggle({ collapsed = false }: ThemeToggleProps) {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Smoothly apply transition helper class to html element during theme swap
  const changeTheme = (nextTheme: "light" | "dark" | "system") => {
    if (typeof document !== "undefined") {
      const root = document.documentElement;
      root.classList.add("theme-transitioning");
      setTheme(nextTheme);
      window.setTimeout(() => {
        root.classList.remove("theme-transitioning");
      }, 300);
    } else {
      setTheme(nextTheme);
    }
  };

  const cycleTheme = () => {
    if (theme === "system") {
      changeTheme("light");
    } else if (theme === "light") {
      changeTheme("dark");
    } else {
      changeTheme("system");
    }
  };

  if (!mounted) {
    return (
      <div
        className={
          collapsed
            ? "flex h-9 w-9 items-center justify-center rounded-lg bg-transparent"
            : "flex h-9 w-full items-center justify-between px-2.5 rounded-lg bg-transparent"
        }
        aria-hidden="true"
      >
        <div className="h-4 w-4 rounded-full bg-muted animate-pulse" />
      </div>
    );
  }

  const isDark = resolvedTheme === "dark";

  if (collapsed) {
    return (
      <TooltipProvider delayDuration={150}>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              onClick={cycleTheme}
              className="h-9 w-9 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted/80 transition-colors"
              aria-label={`Current theme: ${theme}. Click to switch theme.`}
              data-testid="theme-toggle-collapsed"
            >
              {theme === "system" ? (
                <Monitor className="h-4 w-4" />
              ) : isDark ? (
                <Moon className="h-4 w-4 text-primary" />
              ) : (
                <Sun className="h-4 w-4 text-amber-500" />
              )}
            </Button>
          </TooltipTrigger>
          <TooltipContent side="right" sideOffset={10} className="font-medium text-xs">
            Theme: {theme ? theme.charAt(0).toUpperCase() + theme.slice(1) : "System"} (Click to cycle)
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  return (
    <div
      className="flex items-center justify-between w-full p-1 rounded-lg bg-muted/50 border border-border/50 text-xs"
      role="group"
      aria-label="Color theme switcher"
      data-testid="theme-toggle-expanded"
    >
      <button
        type="button"
        onClick={() => changeTheme("light")}
        className={`flex-1 flex items-center justify-center gap-1.5 py-1 px-2 rounded-md font-medium transition-all ${
          theme === "light"
            ? "bg-background text-foreground shadow-sm font-semibold"
            : "text-muted-foreground hover:text-foreground"
        }`}
        aria-pressed={theme === "light"}
        aria-label="Light mode"
      >
        <Sun className="h-3.5 w-3.5 text-amber-500" />
        <span>Light</span>
      </button>

      <button
        type="button"
        onClick={() => changeTheme("dark")}
        className={`flex-1 flex items-center justify-center gap-1.5 py-1 px-2 rounded-md font-medium transition-all ${
          theme === "dark"
            ? "bg-background text-foreground shadow-sm font-semibold"
            : "text-muted-foreground hover:text-foreground"
        }`}
        aria-pressed={theme === "dark"}
        aria-label="Dark mode"
      >
        <Moon className="h-3.5 w-3.5 text-primary" />
        <span>Dark</span>
      </button>

      <button
        type="button"
        onClick={() => changeTheme("system")}
        className={`flex-1 flex items-center justify-center gap-1.5 py-1 px-2 rounded-md font-medium transition-all ${
          theme === "system"
            ? "bg-background text-foreground shadow-sm font-semibold"
            : "text-muted-foreground hover:text-foreground"
        }`}
        aria-pressed={theme === "system"}
        aria-label="System preference mode"
      >
        <Monitor className="h-3.5 w-3.5" />
        <span>Auto</span>
      </button>
    </div>
  );
}
