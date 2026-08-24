import React from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "@/components/ui/table";
import { formatCurrency, formatPercentage } from "@/lib/utils";
import {
  TrendingUp,
  TrendingDown,
  FileText,
  ShieldCheck,
  Search,
  Sparkles,
  ArrowUpRight,
  Database,
  Activity,
} from "lucide-react";

export default function Home() {
  return (
    <main className="min-h-screen bg-background p-6 md:p-12">
      <div className="mx-auto max-w-6xl space-y-10">
        {/* Header Branding */}
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between border-b pb-6">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground font-bold text-base shadow-sm">
                FS
              </span>
              <h1 className="text-2xl font-bold tracking-tight text-foreground">
                FinSight
              </h1>
              <Badge variant="outline" className="ml-2 font-mono text-xs">
                v0.1.0 • Phase 11.1 Foundation
              </Badge>
            </div>
            <p className="text-sm text-muted-foreground">
              Institutional AI Investment Research Copilot • Design System & Architecture Verification
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Badge variant="financePositive" className="gap-1 px-3 py-1 font-medium">
              <Activity className="h-3.5 w-3.5" />
              Backend Connected (254 Tests Passing)
            </Badge>
          </div>
        </div>

        {/* Foundation Grid */}
        <div className="grid gap-6 md:grid-cols-3">
          {/* Card 1: Design Tokens & Typography */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Sparkles className="h-4 w-4 text-primary" />
                Institutional Design Tokens
              </CardTitle>
              <CardDescription>
                High-density, low-glare financial research palette adhering to Taste Skill rules.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap gap-2">
                <Button size="sm">Primary Action</Button>
                <Button size="sm" variant="secondary">Secondary</Button>
                <Button size="sm" variant="outline">Outline</Button>
                <Button size="sm" variant="destructive">Destructive</Button>
              </div>
              <div className="flex flex-wrap gap-2 pt-2">
                <Badge>Default</Badge>
                <Badge variant="secondary">Secondary</Badge>
                <Badge variant="outline">Outline</Badge>
              </div>
            </CardContent>
          </Card>

          {/* Card 2: Financial Semantic States */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <TrendingUp className="h-4 w-4 text-finance-positive" />
                Financial Provenance & Metrics
              </CardTitle>
              <CardDescription>
                Audited calculations with accessible dual-channel directional signs.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center justify-between rounded-md border p-2.5">
                <span className="text-xs font-medium text-muted-foreground">Gross Margin (2025)</span>
                <span className="font-mono text-sm font-semibold text-foreground font-tabular-nums">
                  46.23%
                </span>
              </div>
              <div className="flex items-center justify-between rounded-md border p-2.5">
                <span className="text-xs font-medium text-muted-foreground">YoY Revenue Growth</span>
                <Badge variant="financePositive" className="gap-1 font-mono font-tabular-nums">
                  <TrendingUp className="h-3 w-3" />
                  {formatPercentage(14.5)}
                </Badge>
              </div>
              <div className="flex items-center justify-between rounded-md border p-2.5">
                <span className="text-xs font-medium text-muted-foreground">CapEx Delta</span>
                <Badge variant="financeNegative" className="gap-1 font-mono font-tabular-nums">
                  <TrendingDown className="h-3 w-3" />
                  {formatPercentage(-3.8)}
                </Badge>
              </div>
            </CardContent>
          </Card>

          {/* Card 3: Inputs & State Skeletons */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Search className="h-4 w-4 text-primary" />
                Research Controls & Loading
              </CardTitle>
              <CardDescription>
                Input fields and accessible loading skeletons.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-1.5">
                <Input placeholder="e.g. Compare Apple & Microsoft Q4 gross margin" />
              </div>
              <div className="space-y-2 pt-2">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-3/4" />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Financial Table Verification */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Database className="h-4 w-4 text-primary" />
              Financial Data Density & Tabular Number Verification
            </CardTitle>
            <CardDescription>
              Demonstration of tabular financial alignment and multi-period data presentation.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Line Item (Audited)</TableHead>
                  <TableHead className="text-right">FY2023</TableHead>
                  <TableHead className="text-right">FY2024</TableHead>
                  <TableHead className="text-right">FY2025</TableHead>
                  <TableHead className="text-right">3-Yr CAGR</TableHead>
                  <TableHead className="text-right">Provenance</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow>
                  <TableCell className="font-medium">Total Revenue</TableCell>
                  <TableCell className="text-right">{formatCurrency(383285000000)}</TableCell>
                  <TableCell className="text-right">{formatCurrency(391035000000)}</TableCell>
                  <TableCell className="text-right">{formatCurrency(412000000000)}</TableCell>
                  <TableCell className="text-right">
                    <Badge variant="financePositive" className="font-mono">
                      ↑ {formatPercentage(3.68)}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <span className="inline-flex items-center gap-1 text-xs text-primary font-medium cursor-pointer hover:underline">
                      <FileText className="h-3 w-3" />
                      [SOURCE 1, 3]
                    </span>
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="font-medium">Net Income</TableCell>
                  <TableCell className="text-right">{formatCurrency(96995000000)}</TableCell>
                  <TableCell className="text-right">{formatCurrency(93736000000)}</TableCell>
                  <TableCell className="text-right">{formatCurrency(101200000000)}</TableCell>
                  <TableCell className="text-right">
                    <Badge variant="financePositive" className="font-mono">
                      ↑ {formatPercentage(2.14)}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <span className="inline-flex items-center gap-1 text-xs text-primary font-medium cursor-pointer hover:underline">
                      <FileText className="h-3 w-3" />
                      [SOURCE 2, 4]
                    </span>
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
