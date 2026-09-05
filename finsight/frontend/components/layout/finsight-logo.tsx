import React from "react";

interface FinSightLogoProps {
  size?: number;
  className?: string;
}

export function FinSightLogo({ size = 32, className = "" }: FinSightLogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`shrink-0 ${className}`}
      aria-hidden="true"
    >
      <defs>
        {/* Modern multi-stop gradient aligned with institutional primary tokens */}
        <linearGradient id="fs-logo-bg" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop stopColor="hsl(var(--primary))" />
          <stop offset="1" stopColor="hsl(224 85% 40%)" />
        </linearGradient>

        <linearGradient id="fs-logo-chart" x1="6" y1="24" x2="26" y2="8" gradientUnits="userSpaceOnUse">
          <stop stopColor="#ffffff" />
          <stop offset="1" stopColor="hsl(var(--primary-foreground))" />
        </linearGradient>

        {/* Soft institutional glowing spark */}
        <radialGradient id="fs-spark" cx="0.5" cy="0.5" r="0.5" fx="0.5" fy="0.5">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="1" />
          <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* Rounded squircle backdrop with subtle hairline border */}
      <rect
        x="1"
        y="1"
        width="30"
        height="30"
        rx="8"
        fill="url(#fs-logo-bg)"
        className="transition-colors duration-250"
      />
      <rect
        x="1.5"
        y="1.5"
        width="29"
        height="29"
        rx="7.5"
        stroke="hsl(var(--primary-foreground) / 0.15)"
        strokeWidth="1"
      />

      {/* Financial Bar Chart (Analytical Insight) */}
      <rect x="7" y="18" width="3" height="6" rx="1.2" fill="#ffffff" fillOpacity="0.45" />
      <rect x="12" y="14" width="3" height="10" rx="1.2" fill="#ffffff" fillOpacity="0.75" />
      <rect x="17" y="10" width="3" height="14" rx="1.2" fill="#ffffff" fillOpacity="0.95" />

      {/* Financial Upward Trajectory / Copilot Spark Vector */}
      <path
        d="M7 17.5L12 13.5L17 9.5L25 6"
        stroke="#ffffff"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Copilot Insight Node / Star at the peak */}
      <circle cx="25" cy="6" r="2" fill="#ffffff" />
      <circle cx="25" cy="6" r="3.5" fill="url(#fs-spark)" fillOpacity="0.6" />
    </svg>
  );
}
