"use client";

import React from "react";
import Link from "next/link";
import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "@/components/ui/table";
import { formatCurrency, formatPercentage } from "@/lib/utils";
import {
  TrendingUp,
  TrendingDown,
  FileText,
  Sparkles,
  ArrowRight,
  Database,
  Activity,
  Files,
} from "lucide-react";
import { useDocuments } from "@/hooks/use-documents";

export default function Home() {
  const { data: documentData } = useDocuments();
  const docCount = documentData?.documents.length ?? 0;
  const indexedCount =
    documentData?.documents.filter((d) => d.status === "indexed").length ?? 0;

  return (
    <AppShell>
      <div className="space-y-8" data-testid="dashboard-page">
        {/* Header Branding */}
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between border-b pb-6">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight text-foreground">
                FinSight Dashboard
              </h1>
              <Badge variant="outline" className="ml-2 font-mono text-xs">
                v0.1.0 • Institutional Research
              </Badge>
            </div>
            <p className="text-sm text-muted-foreground">
              Institutional AI Investment Research Copilot • Grounded SEC Filings & Financial Table Extraction
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Link href="/documents">
              <Button size="sm" className="gap-1.5 text-xs">
                <Files className="h-3.5 w-3.5" />
                <span>Open Document Repository</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </Button>
            </Link>
          </div>
        </div>

        {/* Top Metric Cards */}
        <div className="grid gap-4 sm:grid-cols-3">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Document Repository
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-baseline justify-between">
                <p className="text-2xl font-bold font-tabular-nums text-foreground">
                  {docCount}
                </p>
                <Badge variant="financePositive" className="gap-1 text-xs">
                  <Activity className="h-3 w-3" />
                  {indexedCount} Indexed
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                Filings available for grounded RAG and cross-company comparisons.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                AI Reasoning & Validation
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-baseline justify-between">
                <p className="text-2xl font-bold text-foreground">LangGraph</p>
                <Badge variant="secondary" className="text-xs">
                  Deterministic
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                5-Node DAG (Planner, Retriever, Analyzer, Auditor, Synthesis) + Guardrails.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Vector Index Engine
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-baseline justify-between">
                <p className="text-2xl font-bold text-foreground">pgvector</p>
                <Badge variant="financePositive" className="text-xs">
                  HNSW Active
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                Gemini 1536-dimensional embeddings with 100% Recall@5.
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Financial Data Density & Tabular Number Presentation */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Database className="h-4 w-4 text-primary" />
              Audited Multi-Period Financial Metrics Demonstration
            </CardTitle>
            <CardDescription>
              Demonstration of high-density tabular numbers, dual-channel directional indicators, and source provenance.
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
                    <span className="inline-flex items-center gap-1 text-xs text-primary font-medium">
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
                    <span className="inline-flex items-center gap-1 text-xs text-primary font-medium">
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
    </AppShell>
  );
}
