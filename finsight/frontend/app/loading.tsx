import { Loader2 } from "lucide-react";

export default function Loading() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center p-6 text-center">
      <Loader2 className="h-8 w-8 animate-spin text-primary" aria-label="Loading research workspace" />
      <p className="mt-4 text-sm font-medium text-muted-foreground">
        Loading FinSight Workspace...
      </p>
    </div>
  );
}
