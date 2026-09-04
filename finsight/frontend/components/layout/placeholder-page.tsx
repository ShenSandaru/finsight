import React from "react";
import Link from "next/link";
import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Files, ArrowLeft } from "lucide-react";

interface PlaceholderPageProps {
  title: string;
  description: string;
  upcomingPhase: string;
}

export function PlaceholderPage({ title, description, upcomingPhase }: PlaceholderPageProps) {
  return (
    <AppShell>
      <div className="space-y-6">
        <div className="border-b pb-5">
          <h1 className="text-xl font-bold tracking-tight text-foreground">{title}</h1>
          <p className="text-xs text-muted-foreground mt-1">{description}</p>
        </div>

        <Card className="border-dashed">
          <CardHeader className="text-center pb-2">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary mb-2">
              <Files className="h-6 w-6" />
            </div>
            <CardTitle className="text-base">{title} Workspace</CardTitle>
            <CardDescription className="text-xs max-w-sm mx-auto">
              This module is scheduled for development in <span className="font-semibold text-foreground">{upcomingPhase}</span>.
            </CardDescription>
          </CardHeader>
          <CardContent className="text-center pt-2">
            <Link href="/documents">
              <Button size="sm" variant="outline" className="gap-1.5 text-xs">
                <ArrowLeft className="h-3.5 w-3.5" />
                <span>Go to Document Repository</span>
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
