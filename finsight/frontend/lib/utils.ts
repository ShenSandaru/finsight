import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merges Tailwind classes safely with clsx and twMerge.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/**
 * Formats a currency value to standard financial notation.
 * e.g. 1250000000 -> "$1,250,000,000.00"
 */
export function formatCurrency(
  value: number | null | undefined,
  currency = "$",
  decimals = 2
): string {
  if (value === null || value === undefined || isNaN(value)) return "—";
  const formatted = Math.abs(value).toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  if (value < 0) {
    return `(${currency}${formatted})`;
  }
  return `${currency}${formatted}`;
}

/**
 * Formats a percentage value with directional sign.
 * e.g. 14.5 -> "+14.5%", -3.2 -> "-3.2%"
 */
export function formatPercentage(
  value: number | null | undefined,
  decimals = 2,
  includeSign = true
): string {
  if (value === null || value === undefined || isNaN(value)) return "—";
  const sign = includeSign && value > 0 ? "+" : "";
  return `${sign}${value.toFixed(decimals)}%`;
}

/**
 * Formats a financial ratio value.
 * e.g. 2.154 -> "2.15x"
 */
export function formatRatio(
  value: number | null | undefined,
  decimals = 2
): string {
  if (value === null || value === undefined || isNaN(value)) return "—";
  return `${value.toFixed(decimals)}x`;
}
