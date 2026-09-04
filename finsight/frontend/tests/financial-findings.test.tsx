import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import { MetricCard } from "@/components/finance/metric-card";
import { RatioTable } from "@/components/finance/ratio-table";
import { CagrTrendBadge } from "@/components/finance/cagr-trend-badge";
import { FindingList } from "@/components/finance/finding-list";
import {
  formatFinancialValue,
  formatMetricName,
  formatPeriod,
  parseTrendFinding,
} from "@/lib/utils/financial-formatter";
import { FinancialFinding } from "@/types/api";
import { useUiStore } from "@/stores/ui-store";

describe("Phase 11.6 Financial Findings & Trend Visualization Test Suite", () => {
  beforeEach(() => {
    useUiStore.setState({
      citationDrawerOpen: false,
      activeCitationChunkId: null,
      activeCitationContext: null,
    });
  });

  // ============================================================
  // 1. Formatting Utility Tests
  // ============================================================
  describe("Financial Formatting Utilities", () => {
    it("formats currency values into billions, millions, and standard notation", () => {
      expect(formatFinancialValue(412_000_000_000, "$")).toBe("$412.00B");
      expect(formatFinancialValue(126_600_000, "$")).toBe("$126.60M");
      expect(formatFinancialValue(12_500, "$")).toBe("$12.50K");
      expect(formatFinancialValue(450.75, "$")).toBe("$450.75");
      expect(formatFinancialValue(-50_000_000, "$")).toBe("($50.00M)");
    });

    it("formats percentage and ratio values without floating point noise", () => {
      expect(formatFinancialValue(46.2312, "%")).toBe("+46.23%");
      expect(formatFinancialValue(-7.456, "%")).toBe("-7.46%");
      expect(formatFinancialValue(1.524, "ratio")).toBe("1.52x");
      expect(formatFinancialValue(125_000_000, "shares")).toBe("125.00M shares");
    });

    it("formats canonical metric names to institutional titles", () => {
      expect(formatMetricName("revenue")).toBe("Total Revenue");
      expect(formatMetricName("gross_margin")).toBe("Gross Margin");
      expect(formatMetricName("operating_income")).toBe("Operating Income");
      expect(formatMetricName("roa")).toBe("Return on Assets (ROA)");
      expect(formatMetricName("revenue_growth")).toBe("Total Revenue YoY Growth");
      expect(formatMetricName("revenue_cagr")).toBe("Total Revenue CAGR");
      expect(formatMetricName("custom_nonstandard_metric")).toBe("Custom Nonstandard Metric");
    });

    it("formats period strings into clean institutional notation", () => {
      expect(formatPeriod("2025")).toBe("FY2025");
      expect(formatPeriod("2025_vs_2024")).toBe("FY25 vs FY24");
      expect(formatPeriod("2023_to_2025")).toBe("FY23–FY25");
    });

    it("parses authoritative trend findings accurately", () => {
      const incFinding: FinancialFinding = {
        metric: "revenue_trend",
        period: "2023_to_2025",
        value: 1.0,
        unit: "trend",
        source_chunk_ids: ["c1"],
        calculation: "Consistent Increase: [383285 -> 394328 -> 412000]",
      };
      const parsedInc = parseTrendFinding(incFinding);
      expect(parsedInc.direction).toBe("improving");
      expect(parsedInc.glyph).toBe("↑");
      expect(parsedInc.label).toBe("Consistent Increase");
      expect(parsedInc.sequence).toBe("383285 -> 394328 -> 412000");

      const decFinding: FinancialFinding = {
        metric: "margin_trend",
        period: "2023_to_2025",
        value: -1.0,
        unit: "trend",
        source_chunk_ids: ["c2"],
        calculation: "Consistent Decrease: [48.5 -> 46.2 -> 44.1]",
      };
      const parsedDec = parseTrendFinding(decFinding);
      expect(parsedDec.direction).toBe("declining");
      expect(parsedDec.glyph).toBe("↓");

      const volFinding: FinancialFinding = {
        metric: "fcf_trend",
        period: "2023_to_2025",
        value: 0.0,
        unit: "trend",
        source_chunk_ids: ["c3"],
        calculation: "Volatile: [100 -> 80 -> 120]",
      };
      const parsedVol = parseTrendFinding(volFinding);
      expect(parsedVol.direction).toBe("volatile");
      expect(parsedVol.glyph).toBe("~");
    });
  });

  // ============================================================
  // 2. MetricCard Component Tests
  // ============================================================
  describe("MetricCard Component", () => {
    const revenueFinding: FinancialFinding = {
      metric: "revenue",
      period: "2025",
      value: 412000,
      unit: "$",
      source_chunk_ids: ["chunk-rev-1"],
    };

    const growthFinding: FinancialFinding = {
      metric: "revenue_growth",
      period: "2025_vs_2024",
      value: 7.49,
      unit: "%",
      source_chunk_ids: ["chunk-rev-1"],
    };

    const trendFinding: FinancialFinding = {
      metric: "revenue_trend",
      period: "2023_to_2025",
      value: 1.0,
      unit: "trend",
      source_chunk_ids: ["chunk-rev-1"],
      calculation: "Consistent Increase: [383285 -> 394328 -> 412000]",
    };

    it("renders metric name, formatted value, and period badge", () => {
      render(
        <MetricCard finding={revenueFinding} />
      );

      expect(screen.getByText("Total Revenue")).toBeInTheDocument();
      expect(screen.getByTestId("metric-value")).toHaveTextContent("$412.00K");
      expect(screen.getByText("FY2025")).toBeInTheDocument();
    });

    it("renders YoY change indicator when growth finding is provided", () => {
      render(
        <MetricCard finding={revenueFinding} growthFinding={growthFinding} />
      );

      const yoy = screen.getByTestId("metric-yoy-growth");
      expect(yoy).toBeInTheDocument();
      expect(yoy).toHaveTextContent("+7.5%");
    });

    it("triggers citation drawer when clicking evidence button with chunk ID", () => {
      render(
        <MetricCard finding={revenueFinding} />
      );

      const evidenceBtn = screen.getByTestId("metric-evidence-button");
      expect(evidenceBtn).toBeInTheDocument();

      fireEvent.click(evidenceBtn);
      expect(useUiStore.getState().citationDrawerOpen).toBe(true);
      expect(useUiStore.getState().activeCitationChunkId).toBe("chunk-rev-1");
    });

    it("handles missing optional fields cleanly without breaking layout", () => {
      const minimalFinding: FinancialFinding = {
        metric: "custom_metric",
        period: "2025",
        value: 125,
        unit: "$",
        source_chunk_ids: [],
      };

      render(<MetricCard finding={minimalFinding} />);
      expect(screen.getByText("Custom Metric")).toBeInTheDocument();
      expect(screen.getByTestId("metric-value")).toHaveTextContent("$125.00");
      expect(screen.queryByTestId("metric-evidence-button")).not.toBeInTheDocument();
    });
  });

  // ============================================================
  // 3. RatioTable Component Tests
  // ============================================================
  describe("RatioTable Component", () => {
    const ratioFindings: FinancialFinding[] = [
      {
        metric: "gross_margin",
        period: "2024",
        value: 45.12,
        unit: "%",
        source_chunk_ids: ["chunk-ratio-1"],
      },
      {
        metric: "gross_margin",
        period: "2025",
        value: 46.23,
        unit: "%",
        source_chunk_ids: ["chunk-ratio-2"],
      },
      {
        metric: "current_ratio",
        period: "2025",
        value: 1.45,
        unit: "ratio",
        source_chunk_ids: ["chunk-ratio-3"],
      },
    ];

    it("renders multi-period ratio headers and rows without recalculating", () => {
      render(<RatioTable ratioFindings={ratioFindings} />);

      expect(screen.getByText("Financial Ratios & Margins")).toBeInTheDocument();
      expect(screen.getByText("FY2024")).toBeInTheDocument();
      expect(screen.getByText("FY2025")).toBeInTheDocument();

      // Check rows
      expect(screen.getByText("Gross Margin")).toBeInTheDocument();
      expect(screen.getByText("+45.12%")).toBeInTheDocument();
      expect(screen.getByText("+46.23%")).toBeInTheDocument();

      expect(screen.getByText("Current Ratio")).toBeInTheDocument();
      expect(screen.getByText("1.45x")).toBeInTheDocument();
    });

    it("clicking source evidence button triggers citation drawer", () => {
      render(<RatioTable ratioFindings={ratioFindings} />);

      const sourceBtn = screen.getByTestId("evidence-btn-gross_margin");
      expect(sourceBtn).toBeInTheDocument();

      fireEvent.click(sourceBtn);
      expect(useUiStore.getState().citationDrawerOpen).toBe(true);
      expect(useUiStore.getState().activeCitationChunkId).toBe("chunk-ratio-1");
    });
  });

  // ============================================================
  // 4. CagrTrendBadge Component Tests
  // ============================================================
  describe("CagrTrendBadge Component", () => {
    it("renders dual-channel glyph and text label for improving trend", () => {
      render(
        <CagrTrendBadge
          trend={{
            direction: "improving",
            label: "Consistent Increase",
            glyph: "↑",
          }}
          cagrValue={8.5}
        />
      );

      const badge = screen.getByTestId("cagr-trend-badge");
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveAttribute("data-direction", "improving");
      expect(badge).toHaveTextContent("↑");
      expect(badge).toHaveTextContent("+8.5% CAGR");
      expect(badge).toHaveTextContent("Consistent Increase");
    });

    it("renders volatile trend glyph and label", () => {
      render(
        <CagrTrendBadge
          trend={{
            direction: "volatile",
            label: "Volatile",
            glyph: "~",
          }}
        />
      );

      const badge = screen.getByTestId("cagr-trend-badge");
      expect(badge).toHaveAttribute("data-direction", "volatile");
      expect(badge).toHaveTextContent("~");
      expect(badge).toHaveTextContent("Volatile");
    });
  });

  // ============================================================
  // 5. FindingList Component Tests
  // ============================================================
  describe("FindingList Component", () => {
    const findings: FinancialFinding[] = [
      {
        metric: "revenue",
        period: "2025",
        value: 412000,
        unit: "$",
        source_chunk_ids: ["chunk-1"],
      },
      {
        metric: "revenue_growth",
        period: "2025_vs_2024",
        value: 7.49,
        unit: "%",
        source_chunk_ids: ["chunk-1"],
      },
      {
        metric: "gross_margin",
        period: "2025",
        value: 46.23,
        unit: "%",
        source_chunk_ids: ["chunk-2"],
      },
      {
        metric: "revenue_cagr",
        period: "2023_to_2025",
        value: 3.75,
        unit: "%",
        source_chunk_ids: ["chunk-1"],
      },
      {
        metric: "revenue_trend",
        period: "2023_to_2025",
        value: 1.0,
        unit: "trend",
        source_chunk_ids: ["chunk-1"],
        calculation: "Consistent Increase: [383285 -> 394328 -> 412000]",
      },
    ];

    it("organizes findings into metric cards, ratio table, and growth dynamics", () => {
      render(<FindingList findings={findings} />);

      expect(screen.getByTestId("financial-findings-container")).toBeInTheDocument();
      expect(screen.getByText("Audited Financial Findings")).toBeInTheDocument();
      expect(screen.getByTestId("metric-card-revenue")).toBeInTheDocument();
      expect(screen.getByTestId("ratio-table-container")).toBeInTheDocument();
      expect(screen.getByTestId("growth-summary-container")).toBeInTheDocument();
    });

    it("renders nothing when findings array is empty", () => {
      const { container } = render(<FindingList findings={[]} />);
      expect(container.firstChild).toBeNull();
    });
  });
});
