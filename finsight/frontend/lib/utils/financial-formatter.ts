import { FinancialFinding } from "@/types/api";

/**
 * Metric display dictionary mapping canonical backend metric keys to institutional titles.
 */
const METRIC_LABELS: Record<string, string> = {
  revenue: "Total Revenue",
  gross_profit: "Gross Profit",
  operating_income: "Operating Income",
  net_income: "Net Income",
  total_assets: "Total Assets",
  total_current_assets: "Current Assets",
  total_current_liabilities: "Current Liabilities",
  total_liabilities: "Total Liabilities",
  total_stockholders_equity: "Stockholders' Equity",
  operating_cash_flow: "Operating Cash Flow",
  capital_expenditures: "CapEx",
  free_cash_flow: "Free Cash Flow",
  gross_margin: "Gross Margin",
  operating_margin: "Operating Margin",
  net_margin: "Net Margin",
  roa: "Return on Assets (ROA)",
  current_ratio: "Current Ratio",
  debt_to_equity: "Debt-to-Equity",
};

/**
 * Formats canonical metric name (e.g. 'gross_margin' -> 'Gross Margin', 'revenue_growth' -> 'Revenue YoY Growth')
 */
export function formatMetricName(rawMetric: string): string {
  if (!rawMetric) return "Metric";

  // Check direct canonical lookup
  if (METRIC_LABELS[rawMetric]) {
    return METRIC_LABELS[rawMetric];
  }

  // Handle derived metric suffixes
  if (rawMetric.endsWith("_growth")) {
    const base = rawMetric.replace(/_growth$/, "");
    const baseLabel = METRIC_LABELS[base] || formatMetricWords(base);
    return `${baseLabel} YoY Growth`;
  }
  if (rawMetric.endsWith("_cagr")) {
    const base = rawMetric.replace(/_cagr$/, "");
    const baseLabel = METRIC_LABELS[base] || formatMetricWords(base);
    return `${baseLabel} CAGR`;
  }
  if (rawMetric.endsWith("_trend")) {
    const base = rawMetric.replace(/_trend$/, "");
    const baseLabel = METRIC_LABELS[base] || formatMetricWords(base);
    return `${baseLabel} Trend`;
  }

  return formatMetricWords(rawMetric);
}

function formatMetricWords(metric: string): string {
  return metric
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(" ");
}

/**
 * Formats financial period tag (e.g. '2025' -> 'FY2025', '2025_vs_2024' -> 'FY25 vs FY24', '2023_to_2025' -> 'FY23–FY25')
 */
export function formatPeriod(rawPeriod: string): string {
  if (!rawPeriod) return "";

  // Comparison period: e.g. '2025_docB_vs_docA'
  if (rawPeriod.includes("_docB_vs_docA")) {
    const basePeriod = rawPeriod.replace("_docB_vs_docA", "");
    return /^\d{4}$/.test(basePeriod) ? `FY${basePeriod} (Doc B vs Doc A)` : `${basePeriod} (Doc B vs Doc A)`;
  }

  // YoY comparison: '2025_vs_2024'
  if (rawPeriod.includes("_vs_")) {
    const [curr, prev] = rawPeriod.split("_vs_");
    return `FY${curr.slice(-2)} vs FY${prev.slice(-2)}`;
  }

  // Multi-year span: '2023_to_2025'
  if (rawPeriod.includes("_to_")) {
    const [start, end] = rawPeriod.split("_to_");
    return `FY${start.slice(-2)}–FY${end.slice(-2)}`;
  }

  // 4-digit fiscal year: '2025' -> 'FY2025'
  if (/^\d{4}$/.test(rawPeriod)) {
    return `FY${rawPeriod}`;
  }

  return rawPeriod.toUpperCase();
}

/**
 * Formats a financial value based on its unit, preserving precision without floating point noise.
 * Calculations are NOT performed here; this is purely presentation formatting.
 */
export function formatFinancialValue(value: number, unit: string): string {
  if (value === null || value === undefined || isNaN(value)) {
    return "—";
  }

  const normalizedUnit = (unit || "$").trim().toLowerCase();

  // 1. Percentage
  if (normalizedUnit === "%") {
    const sign = value > 0 ? "+" : "";
    return `${sign}${value.toFixed(2)}%`;
  }

  // 2. Ratio
  if (normalizedUnit === "ratio") {
    return `${value.toFixed(2)}x`;
  }

  // 3. Shares
  if (normalizedUnit === "shares") {
    if (Math.abs(value) >= 1_000_000_000) {
      return `${(value / 1_000_000_000).toFixed(2)}B shares`;
    }
    if (Math.abs(value) >= 1_000_000) {
      return `${(value / 1_000_000).toFixed(2)}M shares`;
    }
    return `${value.toLocaleString("en-US")} shares`;
  }

  // 4. Trend
  if (normalizedUnit === "trend") {
    if (value > 0) return "Consistent Increase";
    if (value < 0) return "Consistent Decrease";
    return "Stable / Volatile";
  }

  // 5. Currency ($ or default)
  const abs = Math.abs(value);
  let formatted = "";

  if (abs >= 1_000_000_000) {
    formatted = `$${(abs / 1_000_000_000).toFixed(2)}B`;
  } else if (abs >= 1_000_000) {
    formatted = `$${(abs / 1_000_000).toFixed(2)}M`;
  } else if (abs >= 1_000) {
    formatted = `$${(abs / 1_000).toFixed(2)}K`;
  } else {
    formatted = `$${abs.toFixed(2)}`;
  }

  if (value < 0) {
    return `(${formatted})`;
  }
  return formatted;
}

export type TrendDirection = "improving" | "declining" | "flat" | "volatile" | "neutral";

export interface ParsedTrend {
  direction: TrendDirection;
  label: string;
  glyph: string;
  sequence?: string;
  isIncomplete?: boolean;
}

/**
 * Interprets authoritative backend-derived trend findings without recalculating.
 * Backend stores:
 *   value: 1.0 (improving/increasing), -1.0 (declining/decreasing), 0.0 (flat or volatile)
 *   calculation: "Consistent Increase: [val1 -> val2 -> val3]" or "Volatile: [...]"
 */
export function parseTrendFinding(finding: FinancialFinding): ParsedTrend {
  const calc = finding.calculation || "";
  const val = finding.value;

  const isIncomplete = calc.toLowerCase().includes("incomplete");

  if (calc.toLowerCase().includes("consistent increase") || val > 0) {
    return {
      direction: "improving",
      label: isIncomplete ? "Consistent Increase (Incomplete)" : "Consistent Increase",
      glyph: "↑",
      sequence: extractSequence(calc),
      isIncomplete,
    };
  }

  if (calc.toLowerCase().includes("consistent decrease") || val < 0) {
    return {
      direction: "declining",
      label: isIncomplete ? "Consistent Decrease (Incomplete)" : "Consistent Decrease",
      glyph: "↓",
      sequence: extractSequence(calc),
      isIncomplete,
    };
  }

  if (calc.toLowerCase().includes("flat")) {
    return {
      direction: "flat",
      label: "Flat",
      glyph: "→",
      sequence: extractSequence(calc),
      isIncomplete,
    };
  }

  if (calc.toLowerCase().includes("volatile")) {
    return {
      direction: "volatile",
      label: "Volatile",
      glyph: "~",
      sequence: extractSequence(calc),
      isIncomplete,
    };
  }

  return {
    direction: "neutral",
    label: "Stable",
    glyph: "→",
    sequence: extractSequence(calc),
    isIncomplete,
  };
}

function extractSequence(calc: string): string | undefined {
  const match = calc.match(/\[(.*?)\]/);
  return match ? match[1] : undefined;
}

/**
 * Classification categorization for presentation grouping
 */
export type FindingCategory = "metric" | "ratio" | "growth" | "cagr" | "trend" | "comparison";

export function categorizeFinding(finding: FinancialFinding): FindingCategory {
  const metric = finding.metric.toLowerCase();

  if (metric.endsWith("_comparison") || metric.endsWith("_absolute_difference")) {
    return "comparison";
  }
  if (metric.endsWith("_trend") || finding.unit.toLowerCase() === "trend") {
    return "trend";
  }
  if (metric.endsWith("_cagr")) {
    return "cagr";
  }
  if (metric.endsWith("_growth")) {
    return "growth";
  }
  if (
    finding.unit === "ratio" ||
    metric.includes("margin") ||
    metric === "roa" ||
    metric === "current_ratio" ||
    metric === "debt_to_equity"
  ) {
    return "ratio";
  }

  return "metric";
}
