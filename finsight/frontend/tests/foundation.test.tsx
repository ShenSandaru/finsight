import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { formatCurrency, formatPercentage } from "@/lib/utils";

describe("FinSight Foundation Test Suite", () => {
  it("renders Button component correctly", () => {
    render(<Button>Run Financial Query</Button>);
    expect(
      screen.getByRole("button", { name: /run financial query/i })
    ).toBeInTheDocument();
  });

  it("renders Badge component with financial positive variant", () => {
    render(<Badge variant="financePositive">↑ +14.5% YoY</Badge>);
    expect(screen.getByText(/↑ \+14\.5% YoY/i)).toBeInTheDocument();
  });

  it("formats financial currency and percentages accurately", () => {
    expect(formatCurrency(1250000000)).toBe("$1,250,000,000.00");
    expect(formatCurrency(-450000)).toBe("($450,000.00)");
    expect(formatPercentage(12.4)).toBe("+12.40%");
    expect(formatPercentage(-5.1)).toBe("-5.10%");
  });
});
